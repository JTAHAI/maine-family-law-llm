from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.audit_verification_console import AuditVerificationConsole
from legal.governance.legal_hold import LegalHoldStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]


def test_pass167_verifies_hash_chain_tampering_and_encrypts_scoped_export_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_LEGAL_HOLD_ROOT", str(tmp_path / "holds"))
    monkeypatch.setenv("MFL_RETENTION_ENGINE_ROOT", str(tmp_path / "retention"))
    monkeypatch.setenv("MFL_SIGNED_POLICY_PACK_ROOT", str(tmp_path / "packs"))
    store = LegalHoldStore()
    store.place(tenant_id="fictional-tenant", matter_scope="matter_scope_001", hold_id="hold_001", artifact_ids=["document_001"], authority_ref="authority_001")
    console = AuditVerificationConsole(tmp_path / "audit", encryption_key="0123456789abcdef")
    report = console.verify(tenant_id="fictional-tenant", matter_scope="matter_scope_001")
    assert report["status"] == "review_required"
    assert report["chains"]["legal_holds"]["status"] == "pass"
    exported = console.export_scope_report(report, tenant_id="fictional-tenant")
    assert exported["exported_to_network"] is False
    encrypted = next((tmp_path / "audit").glob("*.json.enc"))
    assert b"fictional-tenant" not in encrypted.read_bytes()
    path = store._path("fictional-tenant"); state = store._load(path); state["audit"][0]["event_type"] = "tampered"
    store._write(path, state)
    tampered = console.verify(tenant_id="fictional-tenant", matter_scope="matter_scope_001")
    assert tampered["status"] == "blocked"
    assert "audit_chain:legal_holds" in tampered["blockers"]


def test_pass167_production_admin_route_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: case_root)
    monkeypatch.setenv("MFL_LEGAL_HOLD_ROOT", str(tmp_path / "holds"))
    monkeypatch.setenv("MFL_RETENTION_ENGINE_ROOT", str(tmp_path / "retention"))
    monkeypatch.setenv("MFL_SIGNED_POLICY_PACK_ROOT", str(tmp_path / "packs"))
    monkeypatch.setenv("MFL_AUDIT_VERIFICATION_ROOT", str(tmp_path / "audit"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.get("/api/admin/audit-verification", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "c" * 32}
    report = client.get("/api/admin/audit-verification", headers=headers)
    assert report.status_code == 200, report.text
    exported = client.post("/api/admin/audit-verification/export", headers={**headers, "X-MFLL-Idempotency-Key": "audit-export-001"})
    assert exported.status_code == 200 and exported.json()["exported_to_network"] is False
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "audit-verification" in (ROOT / relative).read_text(encoding="utf-8")
