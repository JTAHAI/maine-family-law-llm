from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.production import app as production_app
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.reviewer_handoff import ReviewerHandoffStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]


def _manifest(store: ReviewerHandoffStore) -> None:
    store.add(
        {
            "handoff_id": "handoff_001",
            "record_ids": ["record_001"],
            "reviewer_safe_id": "reviewer_001",
            "purpose": "Fictional source-bound reviewer handoff.",
        }
    )


def test_pass171_encrypted_round_trip_is_append_only_and_hash_verified(tmp_path: Path) -> None:
    store = ReviewerHandoffStore(tmp_path, encryption_key="0123456789abcdef")
    _manifest(store)
    exported = store.export_bundle("handoff_001", {"bundle_id": "bundle_001"})
    bundle = exported["bundle"]
    assert exported["delivery"] == "not_sent_local_export_only"
    assert bundle["external_upload"] is False and bundle["review_required"] is True
    comment = store.add_comment(
        "handoff_001",
        {
            "bundle_id": "bundle_001",
            "comment_id": "comment_001",
            "reviewer_safe_id": "reviewer_001",
            "target_kind": "record",
            "target_id": "record_001",
            "body": "Verify the fictional event date against the exact record.",
        },
    )
    assert comment["source_drill_down"]["source_drill_down"]["route"] == "/api/records/record_001/integrity"
    attested = store.attest(
        "handoff_001",
        {
            "bundle_id": "bundle_001",
            "attestation_id": "attestation_001",
            "reviewer_safe_id": "reviewer_001",
            "statement": "I reviewed this fictional bundle and identified follow-up work.",
        },
    )
    assert attested["attestation"]["cryptographically_verified"] is False
    returned = store.reimport(
        "handoff_001",
        {
            "reimport_id": "reimport_001",
            "reviewer_safe_id": "reviewer_001",
            "bundle": bundle,
            "review_note": "Fictional reimport only; no conclusion reached.",
        },
    )
    assert returned["reconciliation"]["status"] == "review_required"
    assert returned["reconciliation"]["automatic_merge"] is False
    assert len(returned["reconciliation"]["lineage"]["reimport_hashes"]) == 1
    tampered = dict(bundle)
    tampered["purpose"] = "Changed after export"
    with pytest.raises(IntakeWorkbenchError, match="reviewer_bundle_hash_invalid"):
        store.reimport(
            "handoff_001",
            {"reimport_id": "reimport_002", "reviewer_safe_id": "reviewer_001", "bundle": tampered},
        )
    encrypted = next((tmp_path / "41_REVIEWER_HANDOFF").glob("*.enc"))
    assert b"fictional event date" not in encrypted.read_bytes()
    inventory = store.inventory()
    assert "body" not in inventory["comments"][0]
    history = store._load()["history"]  # Append-only audit chain is internal by design.
    assert all(row["review_required"] for row in history)
    assert all(row["previous_hash"] == (history[index - 1]["hash"] if index else "") for index, row in enumerate(history))


def test_pass171_production_route_role_scope_inventory_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: case_root)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-acceptance-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "f" * 32,
    }
    created = client.post(
        "/api/reviewer-handoff",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass171-handoff-create"},
        json={"handoff_id": "handoff_001", "record_ids": ["record_001"], "reviewer_safe_id": "reviewer_001", "purpose": "Fictional reviewer handoff."},
    )
    assert created.status_code == 200, created.text
    denied = client.post(
        "/api/reviewer-handoff/handoff_001/export",
        headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass171-viewer-denied"},
        json={"bundle_id": "bundle_001"},
    )
    assert denied.status_code == 403
    exported = client.post(
        "/api/reviewer-handoff/handoff_001/export",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass171-export"},
        json={"bundle_id": "bundle_001"},
    )
    assert exported.status_code == 200, exported.text
    bundle = exported.json()["bundle"]
    comment = client.post(
        "/api/reviewer-handoff/handoff_001/comments",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass171-comment"},
        json={"bundle_id": "bundle_001", "comment_id": "comment_001", "reviewer_safe_id": "reviewer_001", "target_kind": "record", "target_id": "record_001", "body": "Check the exact fictional source."},
    )
    assert comment.status_code == 200, comment.text
    attestation = client.post(
        "/api/reviewer-handoff/handoff_001/attest",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass171-attest"},
        json={"bundle_id": "bundle_001", "attestation_id": "attestation_001", "reviewer_safe_id": "reviewer_001", "statement": "Fictional local review attestation."},
    )
    assert attestation.status_code == 200
    reimported = client.post(
        "/api/reviewer-handoff/handoff_001/reimport",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass171-reimport"},
        json={"reimport_id": "reimport_001", "reviewer_safe_id": "reviewer_001", "bundle": bundle, "review_note": "Fictional review note."},
    )
    assert reimported.status_code == 200, reimported.text
    assert reimported.json()["reconciliation"]["automatic_merge"] is False
    source = client.get("/api/reviewer-handoff/handoff_001/records/record_001/source", headers=headers)
    assert source.status_code == 200 and source.json()["source_drill_down"]["route"] == "/api/records/record_001/integrity"
    reconcile = client.get("/api/reviewer-handoff/handoff_001/reconcile", headers=headers)
    assert reconcile.status_code == 200 and reconcile.json()["status"] == "review_required"
    assert str(case_root) not in reconcile.text
    required = EndpointInventory().required_paths()
    assert ("POST", "/api/reviewer-handoff/{handoff_id}/reimport") in required
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html"):
        assert "reviewer-bundle-roundtrip" in (ROOT / relative).read_text(encoding="utf-8")
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "reviewer-bundle-roundtrip" in text
        assert "reviewer-handoff/${encodeURIComponent(handoffId)}/reimport" in text
