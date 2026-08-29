from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.separation_of_duties import SeparationOfDutiesReceiptStore, evaluate_separation_of_duties


ROOT = Path(__file__).resolve().parents[1]


def _approvals(*, duplicate: bool = False) -> list[dict[str, object]]:
    rows = [
        ("authority_activation", "authority_activator", "authority_owner_001", "authority_artifact_001"),
        ("security_approval", "security_approver", "security_owner_001", "security_artifact_001"),
        ("legal_sign_off", "legal_signer", "legal_owner_001", "legal_artifact_001"),
        ("release_approval", "release_approver", "release_owner_001", "release_artifact_001"),
    ]
    if duplicate:
        rows[3] = ("release_approval", "release_approver", "legal_owner_001", "release_artifact_001")
    return [{"stage": stage, "role": role, "actor_ref": actor, "artifact_ref": artifact, "approved": True} for stage, role, actor, artifact in rows]


def test_pass163_requires_four_distinct_opaque_actors_and_encrypts_tenant_receipt(tmp_path: Path) -> None:
    accepted = evaluate_separation_of_duties(review_id="sod_review_001", approvals=_approvals(), tenant_id="fictional-tenant")
    assert accepted["status"] == "review_required"
    assert accepted["independence_satisfied"] is True
    assert accepted["independent_actor_count"] == 4
    assert accepted["authority_activation_performed"] is False
    blocked = evaluate_separation_of_duties(review_id="sod_review_002", approvals=_approvals(duplicate=True), tenant_id="fictional-tenant")
    assert blocked["status"] == "blocked"
    assert blocked["independence_satisfied"] is False
    assert "legal_owner_001" in blocked["duplicate_actor_refs"]
    receipt = SeparationOfDutiesReceiptStore(tmp_path, encryption_key="0123456789abcdef").record(accepted, tenant_id="fictional-tenant")
    assert receipt["receipt"]["receipt_id"].startswith("sod_")
    encrypted = next(tmp_path.glob("*.json.enc"))
    assert b"authority_owner_001" not in encrypted.read_bytes()


def test_pass163_canonical_production_route_admin_scope_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_SEPARATION_OF_DUTIES_ROOT", str(tmp_path / "receipts"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    payload = {"review_id": "sod_review_003", "approvals": _approvals()}
    denied = client.post("/api/admin/separation-of-duties", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}, json=payload)
    assert denied.status_code == 403
    accepted = client.post("/api/admin/separation-of-duties", headers={"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "c" * 32, "X-MFLL-Idempotency-Key": "separation-of-duties-001"}, json=payload)
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["independence_satisfied"] is True
    assert body["audit_receipt"]["receipt"]["review_required"] is True
    blocked = client.post("/api/admin/separation-of-duties", headers={"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "d" * 32, "X-MFLL-Idempotency-Key": "separation-of-duties-002"}, json={"review_id": "sod_review_004", "approvals": _approvals(duplicate=True)})
    assert blocked.status_code == 200 and blocked.json()["status"] == "blocked"
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "separation-of-duties" in (ROOT / relative).read_text(encoding="utf-8")
