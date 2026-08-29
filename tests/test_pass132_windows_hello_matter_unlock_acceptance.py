from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.security import mint_session_capability
from legal.matter.matter_store import MatterStore, MatterStoreError
from legal.matter.models import Matter
from legal.security.matter_unlock import MatterUnlockBroker
from maine_family_law_llm import api as api_module


class _VerifiedPresence:
    def availability(self) -> dict[str, str]:
        return {"status": "available", "provider": "fictional_windows_hello"}

    def verify(self, reason: str) -> dict[str, str]:
        assert "active Maine Family Law LLM matter" in reason
        return {"status": "verified", "provider": "fictional_windows_hello"}


class _DeniedPresence(_VerifiedPresence):
    def verify(self, reason: str) -> dict[str, str]:
        return {"status": "blocked", "provider": "fictional_windows_hello", "reason": "windows_hello_not_verified"}


def test_encrypted_policy_requires_scoped_ephemeral_presence_before_matter_read(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store_root = tmp_path / "fictional-matter-store"
    store = MatterStore(store_root, project_root=repo, encryption_key="fictional-unlock-key-132")
    matter = Matter(matter_id="matter-unlock", tenant_id="fictional-tenant", title="Fictional unlock matter")
    matter_dir = store.create_matter(matter)
    broker = MatterUnlockBroker(
        store_root,
        root_secret=store.encryptor.passphrase,
        presence_provider=_VerifiedPresence(),
    )

    configured = broker.configure(
        "fictional-tenant",
        "matter-unlock",
        enabled=True,
        fallback_policy="local_vault_recovery",
        approved=True,
    )
    assert configured["enabled"] is True
    assert configured["biometric_data_collected"] is False
    assert configured["session_grant_persisted"] is False
    assert configured["audit"]["verified"] is True
    raw_policy = next((store_root / ".mfl-matter-unlock").rglob("*.json.enc"))
    assert b"fictional-unlock" not in raw_policy.read_bytes()

    with pytest.raises(MatterStoreError, match="matter_unlock_required"):
        store.load_matter(matter_dir)
    unlocked = broker.verify("fictional-tenant", "matter-unlock", approved=True)
    assert unlocked["status"] == "unlocked"
    assert unlocked["unlocked_for_session"] is True
    assert store.load_matter(matter_dir)["title"] == "Fictional unlock matter"
    locked = broker.lock("fictional-tenant", "matter-unlock")
    assert locked["status"] == "locked"
    with pytest.raises(MatterStoreError, match="matter_unlock_required"):
        store.load_matter(matter_dir)


def test_failed_presence_never_creates_an_unlock_grant(tmp_path: Path) -> None:
    broker = MatterUnlockBroker(
        tmp_path / "fictional-matter-store",
        root_secret="fictional-unlock-root-132",
        presence_provider=_DeniedPresence(),
    )
    broker.configure(
        "fictional-tenant", "matter-denied", enabled=True, fallback_policy="admin_recovery_required", approved=True
    )
    with pytest.raises(Exception, match="windows_hello_not_verified"):
        broker.verify("fictional-tenant", "matter-denied", approved=True)
    status = broker.status("fictional-tenant", "matter-denied")
    assert status["unlocked_for_session"] is False
    assert status["fallback_policy"] == "admin_recovery_required"


def test_canonical_unlock_routes_scope_role_session_and_safe_degraded_state(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store_root = tmp_path / "fictional-matter-store"
    store = MatterStore(store_root, project_root=repo, encryption_key="fictional-api-unlock-key-132")
    matter_dir = store.create_matter(Matter(matter_id="matter-api-unlock", tenant_id="local-desktop", title="Fictional API unlock"))
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter_dir)
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("MFL_SECURITY_BACKUP_ROOT", str(tmp_path / "security-backups"))
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-api-unlock-key-132")
    client = TestClient(api_module.app)
    reviewer_headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "local-desktop", "host": "testserver"}

    status = client.get("/api/security/privacy/matter-unlock", headers=reviewer_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "not_enabled"
    assert status.json()["biometric_data_collected"] is False
    assert client.post("/api/security/privacy/matter-unlock/configure", headers=reviewer_headers, json={}).status_code == 403

    action = "security_privacy_matter_unlock_configure"
    capability = mint_session_capability(user_role="admin", tenant_id="local-desktop", matter_id="matter-api-unlock", action=action)
    admin_headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Session-Token": capability.token,
        "X-CSRF-Token": capability.csrf_token,
        "host": "testserver",
    }
    configured = client.post(
        "/api/security/privacy/matter-unlock/configure",
        headers=admin_headers,
        json={"enabled": False, "fallback_policy": "local_vault_recovery", "approved": True},
    )
    assert configured.status_code == 200
    assert configured.json()["enabled"] is False
    assert configured.json()["review_required"] is True


def test_shipped_privacy_ui_exposes_explicit_nonbiometric_unlock_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    source_html = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    shipped_html = (root / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    source_js = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    shipped_js = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert source_html == shipped_html
    assert source_js == shipped_js
    assert 'id="verify-matter-unlock"' in source_html
    assert 'id="lock-matter-unlock"' in source_html
    assert "/api/security/privacy/matter-unlock/${action}" in source_js
    assert "never collects biometric data" in source_html
    assert "windows_hello" not in source_js
