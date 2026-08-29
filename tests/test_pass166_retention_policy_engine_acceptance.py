from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.legal_hold import LegalHoldStore
from legal.governance.retention_policy_engine import RetentionPolicyEngine
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]


def _approval_config(tmp_path: Path) -> Path:
    path = tmp_path / "retention-approval.json"
    path.write_text(json.dumps({"schema_version": "retention_engine_approval_v1", "approved_policy_refs": ["fictional_policy_001"], "maximum_recovery_window_days": 30}), encoding="utf-8")
    return path


def test_pass166_retention_preview_respects_hold_and_apply_is_recoverable_not_destructive(tmp_path: Path, monkeypatch) -> None:
    hold_store = LegalHoldStore(tmp_path / "holds", encryption_key="0123456789abcdef")
    engine = RetentionPolicyEngine(tmp_path / "retention", encryption_key="0123456789abcdef", legal_holds=hold_store)
    hold_store.place(tenant_id="fictional-tenant", matter_scope="matter_scope_001", hold_id="hold_001", artifact_ids=["document_001"], authority_ref="authority_001")
    blocked = engine.preview(tenant_id="fictional-tenant", matter_scope="matter_scope_001", plan_id="plan_001", artifact_ids=["document_001"], policy_ref="fictional_policy_001", recovery_window_days=7)
    assert blocked["status"] == "blocked" and blocked["plan"]["hold_blockers"] == ["document_001"]
    hold_store.release(tenant_id="fictional-tenant", matter_scope="matter_scope_001", hold_id="hold_001", release_authority_ref="release_001")
    preview = engine.preview(tenant_id="fictional-tenant", matter_scope="matter_scope_001", plan_id="plan_002", artifact_ids=["document_001"], policy_ref="fictional_policy_001", recovery_window_days=7)
    assert preview["status"] == "preview"
    unapproved = engine.apply(tenant_id="fictional-tenant", matter_scope="matter_scope_001", plan_id="plan_002", user_confirmed=True)
    assert unapproved["status"] == "blocked" and "retention_policy_not_organization_approved" in unapproved["blockers"]
    monkeypatch.setenv("MFL_RETENTION_APPROVAL_CONFIG", str(_approval_config(tmp_path)))
    active = engine.apply(tenant_id="fictional-tenant", matter_scope="matter_scope_001", plan_id="plan_002", user_confirmed=True)
    assert active["status"] == "recovery_window_active" and active["plan"]["deletion_performed"] is False
    cancelled = engine.cancel(tenant_id="fictional-tenant", matter_scope="matter_scope_001", plan_id="plan_002")
    assert cancelled["status"] == "cancelled"
    encrypted = next((tmp_path / "retention").glob("*.json.enc"))
    assert b"fictional_policy_001" not in encrypted.read_bytes()


def test_pass166_production_admin_route_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: case_root)
    monkeypatch.setenv("MFL_LEGAL_HOLD_ROOT", str(tmp_path / "holds"))
    monkeypatch.setenv("MFL_RETENTION_ENGINE_ROOT", str(tmp_path / "retention"))
    monkeypatch.setenv("MFL_RETENTION_APPROVAL_CONFIG", str(_approval_config(tmp_path)))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "b" * 32}
    created = client.post("/api/document-workspace/documents", headers={**headers, "X-MFLL-Idempotency-Key": "retention-document-create-001"}, json={"title": "Synthetic retention record", "content": "Synthetic text only"})
    assert created.status_code == 200, created.text
    artifact_id = created.json()["document"]["document_id"]
    reviewer = client.post("/api/admin/retention-plans/preview", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}, json={"plan_id": "plan_001", "artifact_ids": [artifact_id], "policy_ref": "fictional_policy_001", "recovery_window_days": 7})
    assert reviewer.status_code == 403
    preview = client.post("/api/admin/retention-plans/preview", headers={**headers, "X-MFLL-Idempotency-Key": "retention-preview-001"}, json={"plan_id": "plan_001", "artifact_ids": [artifact_id], "policy_ref": "fictional_policy_001", "recovery_window_days": 7})
    assert preview.status_code == 200, preview.text
    applied = client.post("/api/admin/retention-plans/plan_001/apply", headers={**headers, "X-MFLL-Idempotency-Key": "retention-apply-001"}, json={"user_confirmed": True})
    assert applied.status_code == 200 and applied.json()["status"] == "recovery_window_active"
    assert applied.json()["plan"]["deletion_performed"] is False
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "retention-plan" in (ROOT / relative).read_text(encoding="utf-8")
