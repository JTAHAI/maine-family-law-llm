from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.addons.workbench import AddonStudioError, AddonStudioStore, _extension_signature_payload


def _write_trust(path: Path, private_key: Ed25519PrivateKey) -> None:
    public = base64.b64encode(
        private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode("ascii")
    path.write_text(json.dumps({"schema_version": "extension_sandbox_trust_v1", "trusted_keys": {"qa-extension-key": public}}), encoding="utf-8")


def _trusted_extension_payload(private_key: Ed25519PrivateKey) -> dict:
    manifest = {
        "extension_id": "metadata_probe",
        "version": "1.0.0",
        "artifact_sha256": hashlib.sha256(b"fictional declarative extension bundle").hexdigest(),
        "permissions": ["matter.metadata.read"],
        "sandbox_contract": {
            "contract_version": "1.0",
            "operations": ["source_metadata_digest"],
            "max_runs_per_matter": 1,
            "memory_limit_kib": 256,
        },
    }
    return {
        "action": "register",
        "manifest": manifest,
        "key_id": "qa-extension-key",
        "signature": base64.b64encode(private_key.sign(_extension_signature_payload(manifest, include_sandbox_contract=True))).decode("ascii"),
    }


def test_pass193_trusted_declarative_sandbox_enforces_permissions_quota_and_revocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    private_key = Ed25519PrivateKey.generate()
    trust = tmp_path / "external-extension-trust.json"
    _write_trust(trust, private_key)
    monkeypatch.setenv("MFL_EXTENSION_TRUST_CONFIG", str(trust))
    store = AddonStudioStore(matter, tenant_id="tenant_alpha", encryption_key="pass193-test-encryption-key")
    registered = store.execute("extension_sdk_permission_center", _trusted_extension_payload(private_key), actor_role="reviewer")
    assert registered["status"] == "registered_disabled"
    assert registered["trusted_signature_verified"] is True
    assert registered["sandbox_contract"]["network_allowed"] is False
    enabled = store.execute("extension_sdk_permission_center", {"action": "enable", "extension_id": "metadata_probe", "confirmed": True}, actor_role="reviewer")
    assert enabled["enabled"] is True
    source_hash = hashlib.sha256(b"fictional source metadata").hexdigest()
    ran = store.execute("extension_sdk_permission_center", {"action": "sandbox_run", "extension_id": "metadata_probe", "operation": "source_metadata_digest", "source_id": "record_001", "source_sha256": source_hash}, actor_role="reviewer")
    assert ran["status"] == "completed_review_required"
    assert ran["source_drill_down"]["source_sha256"] == source_hash
    assert ran["quota"] == {"used": 1, "maximum": 1}
    assert ran["network_used"] is False
    assert ran["tool_access"] == "none"
    with pytest.raises(AddonStudioError, match="extension_sandbox_quota_exhausted"):
        store.execute("extension_sdk_permission_center", {"action": "sandbox_run", "extension_id": "metadata_probe", "operation": "source_metadata_digest", "source_id": "record_002", "source_sha256": source_hash}, actor_role="reviewer")
    revoked = store.execute("extension_sdk_permission_center", {"action": "revoke", "extension_id": "metadata_probe", "confirmed": True}, actor_role="reviewer")
    assert revoked["enabled"] is False
    raw = (matter / "55_ADDON_STUDIO" / "addon-studio.json.enc").read_text(encoding="utf-8")
    assert "metadata_probe" not in raw and "record_001" not in raw


def test_pass193_legacy_self_supplied_key_cannot_enable_or_run(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    key = Ed25519PrivateKey.generate()
    manifest = {
        "extension_id": "legacy_probe",
        "version": "1.0.0",
        "artifact_sha256": hashlib.sha256(b"legacy").hexdigest(),
        "permissions": ["matter.metadata.read"],
    }
    payload = {
        "manifest": manifest,
        "public_key": base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii"),
        "signature": base64.b64encode(key.sign(_extension_signature_payload(manifest, include_sandbox_contract=False))).decode("ascii"),
    }
    store = AddonStudioStore(matter, tenant_id="tenant_alpha", encryption_key="pass193-test-encryption-key")
    registered = store.execute("extension_sdk_permission_center", payload, actor_role="reviewer")
    assert registered["signature_verified"] is True
    assert registered["trusted_signature_verified"] is False
    with pytest.raises(AddonStudioError, match="extension_trust_verification_required"):
        store.execute("extension_sdk_permission_center", {"action": "enable", "extension_id": "legacy_probe", "confirmed": True}, actor_role="reviewer")


def test_pass193_production_addon_route_and_workbench_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.production import app
    from maine_family_law_llm import api as api_module

    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    private_key = Ed25519PrivateKey.generate()
    trust = tmp_path / "external-extension-trust.json"
    _write_trust(trust, private_key)
    monkeypatch.setenv("MFL_EXTENSION_TRUST_CONFIG", str(trust))
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "pass193-test-encryption-key")
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter)
    client = TestClient(app)
    assert client.post("/api/addons/extension_sdk_permission_center/actions", json={}).status_code == 403
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant_alpha"}
    registered = client.post("/api/addons/extension_sdk_permission_center/actions", headers=headers, json=_trusted_extension_payload(private_key))
    assert registered.status_code == 200
    enabled = client.post("/api/addons/extension_sdk_permission_center/actions", headers=headers, json={"action": "enable", "extension_id": "metadata_probe", "confirmed": True})
    assert enabled.status_code == 200
    ran = client.post("/api/addons/extension_sdk_permission_center/actions", headers=headers, json={"action": "sandbox_run", "extension_id": "metadata_probe", "operation": "source_metadata_digest", "source_id": "record_001", "source_sha256": hashlib.sha256(b"fictional source").hexdigest()})
    assert ran.status_code == 200
    body = ran.json()
    assert body["review_required"] is True
    assert body["status"] == "completed_review_required"
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "Extension SDK sandbox" in text
        assert "source_metadata_digest" in text
