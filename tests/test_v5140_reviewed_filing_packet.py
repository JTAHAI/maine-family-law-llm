from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.documents.workspace import commit_revision, create_document, propose_revision
from legal.review import (
    ReviewedFilingPacketError,
    ReviewedFilingPacketStore,
    build_incremental_review_diff,
    commit_review_decision,
    prepare_review_request,
)
from maine_family_law_llm import api as api_module


def _authority_result() -> dict:
    return {
        "status": "review_required",
        "sources": [
            {
                "source_id": "form-fm-001",
                "title": "Maine court form FM-001",
                "source_class": "court_form",
                "freshness_status": "current",
                "version_date": "07/2026",
                "authority_status": "verified_official_maine",
            }
        ],
        "verification_report": {
            "citations": [],
            "quotes": [],
            "claims": [
                {
                    "claim_id": "claim-001",
                    "statement": "The draft requests enforcement of the current order.",
                    "support_status": "supported",
                    "claim_type": "legal",
                    "source_ids": ["authority-order-enforcement"],
                }
            ],
            "blockers": [],
        },
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": True,
                "citations_resolved": True,
                "quotes_found": True,
                "legal_claims_supported": True,
            },
            "blockers": [],
        },
        "review_required": True,
    }


def _reviewed_document(case: Path) -> dict:
    document = create_document(
        case,
        title="Motion for Contempt",
        content="Motion for contempt. The draft requests enforcement of the current order. Use FM-001.",
        document_type="motion",
    )
    prepared = prepare_review_request(
        case,
        document["document_id"],
        authority_result=_authority_result(),
        facts=["The child changed schools."],
        records=[
            {
                "evidence_id": "record-001",
                "title": "School email",
                "source_locator": "school-email.txt",
                "source_hash": "a" * 64,
                "page_number": 1,
                "text_excerpt": "The child changed schools.",
            }
        ],
    )
    commit_review_decision(
        case,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="approve_review",
        reviewer_name="Reviewer A",
        reviewer_role="attorney",
        attested=True,
        claim_annotations=[{"claim_id": "claim-001", "status": "accepted"}],
    )
    return document


def _commit_edit(case: Path, document: dict, content: str) -> dict:
    proposal = propose_revision(
        case,
        document["document_id"],
        content=content,
        base_revision_id=document["current_revision_id"],
    )
    return commit_revision(
        case,
        document["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )


def test_incremental_diff_marks_prior_review_stale_and_isolates_changed_units(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case)
    _commit_edit(
        case,
        document,
        "Motion for contempt. The draft requests modification instead of enforcement. Use FM-002.",
    )

    result = build_incremental_review_diff(case, document["document_id"])
    assert result["prior_approval_stale"] is True
    assert result["diff"]["changes_count"] > 0
    assert "FM-002" in result["changed_form_ids"]
    assert all(row["prior_review_not_carried_forward"] for row in result["review_units"]["units"])
    assert result["review_required"] is True
    assert result["filing_ready"] is False


def test_assignment_is_revision_bound_and_exclusive_collision_fails_closed(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(case, title="Draft", content="Working draft", document_type="draft")
    store = ReviewedFilingPacketStore(case)
    first = store.assign(
        document["document_id"],
        reviewer_label="Reviewer A",
        role="attorney",
        capabilities=["review", "approve_review"],
        expected_revision_id=document["current_revision_id"],
        exclusive=True,
    )
    assert first["identity_verified"] is False
    with pytest.raises(ReviewedFilingPacketError, match="exclusive active reviewer"):
        store.assign(
            document["document_id"],
            reviewer_label="Reviewer B",
            role="paralegal",
            capabilities=["review"],
            expected_revision_id=document["current_revision_id"],
            exclusive=True,
        )
    assignments = store.assignments_for(document["document_id"])
    assert len(assignments["active"]) == 1
    assert "does not verify" in assignments["identity_notice"]


def test_packet_build_is_deterministic_blocked_after_edit_and_tamper_detected(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case)
    edited = _commit_edit(case, document, "Motion for contempt changed. Use FM-002.")
    store = ReviewedFilingPacketStore(case)
    store.assign(
        document["document_id"],
        reviewer_label="Reviewer A",
        role="attorney",
        capabilities=["review", "export_packet"],
        expected_revision_id=edited["current_revision_id"],
        exclusive=True,
    )

    result = store.build(document["document_id"], approved=True)
    packet = result["packet"]
    assert packet["status"] == "reviewed_packet_blocked"
    assert "prior_review_stale_after_revision_change" in packet["blockers"]
    assert packet["filing_ready"] is False
    assert packet["filing_gate"]["blocker_panel"]["panel_title"] == "Filing gate blockers"
    assert packet["filing_gate"]["blocked_export_explanation"] == packet["filing_gate"]["blockers"]
    assert packet["workflow_blockers"]
    assert store.build(document["document_id"], approved=True)["build_id"] == result["build_id"]
    assert store.verify(result["build_id"])["status"] == "pass"

    packet_path, _ = store.resolve_artifact(result["build_id"], "reviewed-filing-packet.json")
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    payload["document_title"] = "tampered"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")
    assert store.verify(result["build_id"])["status"] == "blocked"
    with pytest.raises(ReviewedFilingPacketError, match="failed verification"):
        store.resolve_artifact(result["build_id"], "reviewed-filing-packet.html")


def test_api_and_ui_expose_reviewed_filing_packet(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(case, title="Draft", content="Working draft", document_type="draft")
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    client = TestClient(api_module.app)

    status = client.get(f"/api/reviewed-filing-packet/status?document_id={document['document_id']}")
    assert status.status_code == 200
    assert status.json()["incremental_review"]["target_revision_id"] == document["current_revision_id"]

    assigned = client.post(
        f"/api/reviewed-filing-packet/documents/{document['document_id']}/assignments",
        json={
            "reviewer_label": "Reviewer A",
            "role": "attorney",
            "capabilities": ["review", "export_packet"],
            "expected_revision_id": document["current_revision_id"],
            "exclusive": True,
        },
    )
    assert assigned.status_code == 200

    built = client.post(
        f"/api/reviewed-filing-packet/documents/{document['document_id']}/build",
        json={"approved": True},
    )
    assert built.status_code == 200
    assert built.json()["packet"]["review_required"] is True
    assert built.json()["artifacts"]

    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="filing-packet-build"' in html
    assert "/api/reviewed-filing-packet" in js
    assert "prior approval not carried forward" in js
    assert ".filing-packet-unit" in css


def test_packet_lifecycle_blocks_changed_authority_removed_form_and_deleted_fact_source(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case)
    # The review fixture did not include a build ID; bind one directly in the consumed request
    # and re-hash the request to exercise generation lifecycle checks.
    review_root = case / "19_DOCUMENT_WORKSPACE" / "reviews" / document["document_id"] / "requests"
    request_path = next(review_root.glob("*.json"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["packet"]["authority_verification"]["build_id"] = "a" * 24
    request.pop("request_sha256", None)
    import hashlib
    request["request_sha256"] = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True), encoding="utf-8")

    store = ReviewedFilingPacketStore(case)
    store.assign(
        document["document_id"],
        reviewer_label="Reviewer A",
        role="attorney",
        capabilities=["review", "export_packet"],
        expected_revision_id=document["current_revision_id"],
        exclusive=True,
    )
    result = store.build(
        document["document_id"],
        approved=True,
        current_authority_build_id="b" * 24,
        current_forms=[],
        current_records=[],
    )
    blockers = result["packet"]["blockers"]
    assert any(item.startswith("authority_generation_changed:") for item in blockers)
    assert "form_removed_from_current_generation:FM-001" in blockers
    assert "fact_source_deleted_or_unavailable:record-001" in blockers
