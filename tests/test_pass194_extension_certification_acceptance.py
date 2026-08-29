from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.addons.workbench import AddonStudioError, AddonStudioStore, _extension_signature_payload


def _trust(path: Path, key: Ed25519PrivateKey) -> None:
    encoded = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    path.write_text(json.dumps({"schema_version": "extension_sandbox_trust_v1", "trusted_keys": {"certification-key": encoded}}), encoding="utf-8")


def _payload(key: Ed25519PrivateKey) -> dict:
    manifest = {
        "extension_id": "certified_probe",
        "version": "1.0.0",
        "artifact_sha256": hashlib.sha256(b"fictional certified declaration").hexdigest(),
        "permissions": ["matter.metadata.read"],
        "sandbox_contract": {
            "contract_version": "1.0",
            "operations": ["source_metadata_digest"],
            "max_runs_per_matter": 2,
            "memory_limit_kib": 256,
            "dependencies": [],
            "user_boundary": "Review required. No network access is allowed.",
        },
    }
    return {"action": "register", "manifest": manifest, "key_id": "certification-key", "signature": base64.b64encode(key.sign(_extension_signature_payload(manifest, include_sandbox_contract=True))).decode("ascii")}


def _admission(key: Ed25519PrivateKey, certificate: dict) -> dict:
    value = {
        "extension_id": "certified_probe",
        "manifest_sha256": certificate["manifest_sha256"],
        "certificate_sha256": certificate["certificate_sha256"],
        "admission_id": "admission_001",
        "decision": "admitted_review_required",
    }
    value["signature"] = {"key_id": "certification-key", "signature": base64.b64encode(key.sign(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())).decode("ascii")}
    return value


def test_pass194_certification_and_external_signed_admission_are_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    key = Ed25519PrivateKey.generate(); trust = tmp_path / "external-trust.json"; _trust(trust, key)
    monkeypatch.setenv("MFL_EXTENSION_TRUST_CONFIG", str(trust))
    store = AddonStudioStore(matter, tenant_id="tenant_alpha", encryption_key="pass194-test-encryption-key")
    registered = store.execute("extension_sdk_permission_center", _payload(key), actor_role="reviewer")
    assert registered["trusted_signature_verified"] is True
    certificate = store.execute("extension_sdk_permission_center", {"action": "certification_assess", "extension_id": "certified_probe"}, actor_role="reviewer")
    assert certificate["status"] == "certification_review_required", certificate
    assert certificate["static_scan"]["status"] == "pass"
    assert certificate["dependency_audit"]["status"] == "pass"
    assert certificate["adversarial"]["status"] == "pass"
    assert certificate["ux_review"]["status"] == "pass"
    assert certificate["admission_verified"] is False
    admitted = store.execute("extension_sdk_permission_center", {"action": "admission_verify", "extension_id": "certified_probe", "admission": _admission(key, certificate)}, actor_role="reviewer")
    assert admitted["status"] == "admitted_review_required"
    assert admitted["admission_verified"] is True
    bad = _admission(key, certificate); bad["decision"] = "filing_ready"
    with pytest.raises(AddonStudioError, match="extension_admission_signature_invalid"):
        store.execute("extension_sdk_permission_center", {"action": "admission_verify", "extension_id": "certified_probe", "admission": bad}, actor_role="reviewer")


def test_pass194_production_ui_entry_uses_canonical_addon_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.production import app
    from maine_family_law_llm import api as api_module

    matter = tmp_path / "fictional-matter"; matter.mkdir()
    key = Ed25519PrivateKey.generate(); trust = tmp_path / "external-trust.json"; _trust(trust, key)
    monkeypatch.setenv("MFL_EXTENSION_TRUST_CONFIG", str(trust))
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "pass194-test-encryption-key")
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter)
    client = TestClient(app); headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant_alpha"}
    assert client.post("/api/addons/extension_sdk_permission_center/actions", json={}).status_code == 403
    assert client.post("/api/addons/extension_sdk_permission_center/actions", headers=headers, json=_payload(key)).status_code == 200
    assessed = client.post("/api/addons/extension_sdk_permission_center/actions", headers=headers, json={"action": "certification_assess", "extension_id": "certified_probe"})
    assert assessed.status_code == 200
    assert assessed.json()["review_required"] is True
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "extension-certification-control" in text
        assert "certification_assess" in text
