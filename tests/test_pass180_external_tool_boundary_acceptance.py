from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.external_tool_boundary import ExternalToolBoundaryStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64
HASH_B = "b" * 64


def _payload(*, reported: bool = False) -> dict:
    return {
        "receipt_id": "boundary_001",
        "export_id": "evidence_export_001",
        "export_hash": HASH_A,
        "actor_safe_id": "reviewer_001",
        "destination_class": "email",
        "purpose": "Fictional review-only handoff boundary.",
        "privacy_risk_acknowledged": True,
        "self_reported_external_transfer": reported,
        "source_refs": [{"source_hash": HASH_B, "source_ref": {"record_id": "record_001", "span": "p. 1"}}],
    }


def test_pass180_boundary_receipt_is_encrypted_and_never_claims_app_transfer(tmp_path: Path) -> None:
    store = ExternalToolBoundaryStore(tmp_path, encryption_key="0123456789abcdef")
    planned = store.record(_payload())
    assert planned["network_action"] is False
    assert planned["receipt"]["transfer_status"] == "planned_not_performed"
    assert planned["receipt"]["destination_address_stored"] is False
    self_reported = store.record(_payload(reported=True) | {"receipt_id": "boundary_002"})
    assert self_reported["receipt"]["transfer_status"] == "self_reported_transfer_unverified"
    assert store.get("boundary_001")["receipt"]["source_refs"][0]["source_ref"]["record_id"] == "record_001"
    encrypted = next((tmp_path / "52_EXTERNAL_TOOL_BOUNDARIES").glob("*.enc"))
    assert b"Fictional review-only" not in encrypted.read_bytes()
    with pytest.raises(IntakeWorkbenchError, match="privacy_acknowledgement_required"):
        store.record(_payload() | {"receipt_id": "boundary_003", "privacy_risk_acknowledged": False})


def test_pass180_production_routes_deny_viewer_and_ship_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "k" * 32}
    assert client.post("/api/external-tool-boundaries", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass180-denied"}, json=_payload()).status_code == 403
    created = client.post("/api/external-tool-boundaries", headers={**headers, "X-MFLL-Idempotency-Key": "pass180-create"}, json=_payload())
    assert created.status_code == 200, created.text
    assert created.json()["receipt"]["transfer_status"] == "planned_not_performed"
    opened = client.get("/api/external-tool-boundaries/boundary_001", headers=headers)
    assert opened.status_code == 200 and opened.json()["network_action"] is False
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "external-tool-boundary-controls" in text
        assert "/api/external-tool-boundaries" in text
        assert "destination address not stored" in text
