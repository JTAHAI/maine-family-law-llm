from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.security import mint_session_capability
from legal.matter.matter_store import MatterStore
from legal.matter.models import Matter
from legal.security.matter_key_hierarchy import MatterKeyHierarchy, MatterKeyHierarchyError
from legal.security.privacy_fortress import MatterSecurityFortress
from maine_family_law_llm import api as api_module


def test_per_matter_keys_separate_rotate_recover_revoke_and_destroy(tmp_path: Path) -> None:
    hierarchy = MatterKeyHierarchy(tmp_path / "fictional-matter-store", root_secret="fictional-root-secret-131")
    envelope_a = hierarchy.encrypt_json("fictional-tenant", "matter-alpha", "matter_document", {"label": "fictional alpha"})
    envelope_b = hierarchy.encrypt_json("fictional-tenant", "matter-beta", "matter_document", {"label": "fictional beta"})
    before_a = hierarchy.status("fictional-tenant", "matter-alpha")
    before_b = hierarchy.status("fictional-tenant", "matter-beta")

    assert before_a["active_key_id"] != before_b["active_key_id"]
    assert hierarchy.decrypt_json("fictional-tenant", "matter-alpha", "matter_document", envelope_a)["label"] == "fictional alpha"
    with pytest.raises(MatterKeyHierarchyError):
        hierarchy.decrypt_json("fictional-tenant", "matter-beta", "matter_document", envelope_a)

    hierarchy.enroll_recovery("fictional-tenant", "matter-alpha", "fictional-recovery-secret-131")
    with pytest.raises(MatterKeyHierarchyError, match="recovery_rewrap_required"):
        hierarchy.rotate("fictional-tenant", "matter-alpha")
    rotated = hierarchy.rotate(
        "fictional-tenant", "matter-alpha", recovery_secret="fictional-recovery-secret-131"
    )
    assert rotated["active_key_id"] != before_a["active_key_id"]
    assert hierarchy.decrypt_json("fictional-tenant", "matter-alpha", "matter_document", envelope_a)["label"] == "fictional alpha"
    hierarchy.recover_root_wrapping("fictional-tenant", "matter-alpha", "fictional-recovery-secret-131")
    with pytest.raises(MatterKeyHierarchyError, match="recovery_secret_invalid"):
        hierarchy.recover_root_wrapping("fictional-tenant", "matter-alpha", "wrong-fictional-secret")

    hierarchy.revoke("fictional-tenant", "matter-alpha")
    with pytest.raises(MatterKeyHierarchyError, match="matter_key_unavailable"):
        hierarchy.decrypt_json("fictional-tenant", "matter-alpha", "matter_document", envelope_a)
    assert hierarchy.decrypt_json("fictional-tenant", "matter-beta", "matter_document", envelope_b)["label"] == "fictional beta"

    envelope_c = hierarchy.encrypt_json("fictional-tenant", "matter-charlie", "matter_document", {"label": "fictional charlie"})
    with pytest.raises(MatterKeyHierarchyError, match="confirmation_required"):
        hierarchy.cryptographic_delete("fictional-tenant", "matter-charlie", approved=True, confirmation="DELETE wrong")
    deleted = hierarchy.cryptographic_delete(
        "fictional-tenant", "matter-charlie", approved=True, confirmation="DELETE matter-charlie"
    )
    assert deleted["status"] == "cryptographically_deleted"
    assert deleted["audit"]["verified"] is True
    assert deleted["key_material_exported"] is False
    with pytest.raises(MatterKeyHierarchyError, match="matter_key_unavailable"):
        hierarchy.decrypt_json("fictional-tenant", "matter-charlie", "matter_document", envelope_c)
    assert hierarchy.decrypt_json("fictional-tenant", "matter-beta", "matter_document", envelope_b)["label"] == "fictional beta"


def test_matter_store_and_fortress_keep_hierarchy_scoped_and_audited(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store_root = tmp_path / "fictional-matter-store"
    store = MatterStore(store_root, project_root=repo, encryption_key="fictional-store-key-131")
    matter = Matter(matter_id="matter-alpha", tenant_id="fictional-tenant", title="Fictional Alpha Matter")
    matter_dir = store.create_matter(matter)

    raw = json.loads((matter_dir / "matter.json.enc").read_text(encoding="utf-8"))
    assert raw["schema_version"] == "matter_key_hierarchy_v1"
    assert "Fictional Alpha Matter" not in json.dumps(raw)
    assert store.load_matter(matter_dir)["title"] == "Fictional Alpha Matter"

    fortress = MatterSecurityFortress(
        matter_dir,
        backup_root=tmp_path / "security-backups",
        project_root=repo,
        encryption_key="fictional-store-key-131",
    )
    status = fortress.matter_key_status(
        matter_id="matter-alpha", tenant_id="fictional-tenant", user_role="reviewer"
    )
    assert status["status"] == "active"
    assert status["audit"]["verified"] is True
    assert status["recovery_secret_exported"] is False
    denied = fortress.matter_key_status(
        matter_id="matter-alpha", tenant_id="other-fictional-tenant", user_role="reviewer"
    )
    assert denied["status"] == "blocked"
    assert denied["blockers"] == ["matter_access_denied"]


def test_canonical_key_routes_require_scope_admin_session_and_review(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store_root = tmp_path / "fictional-matter-store"
    store = MatterStore(store_root, project_root=repo, encryption_key="fictional-api-key-131")
    matter = Matter(matter_id="matter-api", tenant_id="local-desktop", title="Fictional API Matter")
    matter_dir = store.create_matter(matter)
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter_dir)
    # The canonical route loads the checked-in injection policy from the
    # project root; the fictional matter store remains outside that root.
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("MFL_SECURITY_BACKUP_ROOT", str(tmp_path / "security-backups"))
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-api-key-131")
    client = TestClient(api_module.app)
    reviewer_headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "local-desktop", "host": "testserver"}

    status = client.get("/api/security/privacy/matter-key", headers=reviewer_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "active"
    assert status.json()["review_required"] is True
    assert status.json()["key_material_exported"] is False
    assert client.post("/api/security/privacy/matter-key/rotate", headers=reviewer_headers, json={}).status_code == 403

    action = "security_privacy_matter_key_enroll_recovery"
    capability = mint_session_capability(
        user_role="admin", tenant_id="local-desktop", matter_id="matter-api", action=action
    )
    admin_headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Session-Token": capability.token,
        "X-CSRF-Token": capability.csrf_token,
        "host": "testserver",
    }
    enrolled = client.post(
        "/api/security/privacy/matter-key/enroll_recovery",
        headers=admin_headers,
        json={"recovery_secret": "fictional-api-recovery-131", "approved": True},
    )
    assert enrolled.status_code == 200
    assert enrolled.json()["recovery_enabled"] is True
    assert enrolled.json()["recovery_secret_exported"] is False
    assert enrolled.json()["audit_event"]["audit_status"] == "emitted"


def test_shipped_privacy_ui_exposes_only_nonsecret_active_matter_status() -> None:
    root = Path(__file__).resolve().parents[1]
    source_html = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    shipped_html = (root / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    source_js = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    shipped_js = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert source_html == shipped_html
    assert source_js == shipped_js
    assert 'id="refresh-matter-key-status"' in source_html
    assert 'id="matter-key-status-detail"' in source_html
    assert "/api/security/privacy/matter-key" in source_js
    assert "key_material_exported" not in source_js
    assert "recovery_secret" not in source_js
