from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.legal_hold import LegalHoldStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]


def test_pass165_encrypted_hold_register_blocks_and_releases_selected_artifact(tmp_path: Path) -> None:
    store = LegalHoldStore(tmp_path, encryption_key="0123456789abcdef")
    placed = store.place(tenant_id="fictional-tenant", matter_scope="matter_scope_001", hold_id="hold_001", artifact_ids=["document_001"], authority_ref="authority_001")
    assert placed["deletion_prevented"] is True
    assert store.deletion_check(matter_scope="matter_scope_001", artifact_id="document_001")["allowed"] is False
    encrypted = next(tmp_path.glob("*.json.enc"))
    assert b"authority_001" not in encrypted.read_bytes()
    released = store.release(tenant_id="fictional-tenant", matter_scope="matter_scope_001", hold_id="hold_001", release_authority_ref="release_001")
    assert released["deletion_prevented"] is False
    assert store.deletion_check(matter_scope="matter_scope_001", artifact_id="document_001")["allowed"] is True


def test_pass165_production_hold_blocks_actual_document_workspace_delete_path(tmp_path: Path, monkeypatch) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: case_root)
    monkeypatch.setenv("MFL_LEGAL_HOLD_ROOT", str(tmp_path / "holds"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    local_headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "f" * 32}
    created = client.post("/api/document-workspace/documents", headers={**local_headers, "X-MFLL-Idempotency-Key": "hold-document-create-001"}, json={"title": "Fictional preserved draft", "content": "Synthetic text only"})
    assert created.status_code == 200, created.text
    document_id = created.json()["document"]["document_id"]
    denied = client.post("/api/admin/legal-holds", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}, json={"hold_id": "hold_001", "artifact_ids": [document_id], "authority_ref": "authority_001"})
    assert denied.status_code == 403
    admin_headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "a" * 32, "X-MFLL-Idempotency-Key": "hold-place-001"}
    placed = client.post("/api/admin/legal-holds", headers=admin_headers, json={"hold_id": "hold_001", "artifact_ids": [document_id], "authority_ref": "authority_001"})
    assert placed.status_code == 200, placed.text
    blocked = client.post(f"/api/document-workspace/documents/{document_id}/delete-request", headers={**local_headers, "X-MFLL-Idempotency-Key": "hold-delete-request-001"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "legal_hold_active"
    released = client.post("/api/admin/legal-holds/hold_001/release", headers={**admin_headers, "X-MFLL-Idempotency-Key": "hold-release-001"}, json={"release_authority_ref": "release_001"})
    assert released.status_code == 200, released.text
    request = client.post(f"/api/document-workspace/documents/{document_id}/delete-request", headers={**local_headers, "X-MFLL-Idempotency-Key": "hold-delete-request-002"})
    assert request.status_code == 200, request.text
    deleted = client.post(f"/api/document-workspace/documents/{document_id}/delete", headers={**local_headers, "X-MFLL-Idempotency-Key": "hold-delete-001"}, json={"confirmation_token": request.json()["confirmation_token"], "confirmed": True})
    assert deleted.status_code == 200
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "legal-hold" in (ROOT / relative).read_text(encoding="utf-8")
