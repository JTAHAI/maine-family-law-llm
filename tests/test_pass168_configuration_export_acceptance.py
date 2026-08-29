from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.configuration_export import ConfigurationExportService, signed_payload


ROOT = Path(__file__).resolve().parents[1]


def _trust(tmp_path: Path) -> tuple[Path, Ed25519PrivateKey]:
    private = Ed25519PrivateKey.generate(); public = private.public_key().public_bytes_raw()
    path = tmp_path / "trust.json"; path.write_text(json.dumps({"schema_version": "enterprise_configuration_export_trust_v1", "trusted_keys": {"fictional_key_001": base64.b64encode(public).decode("ascii")}}), encoding="utf-8")
    return path, private


def test_pass168_privacy_safe_manifest_verifies_external_signature_and_encrypts_receipt(tmp_path: Path, monkeypatch) -> None:
    trust, private = _trust(tmp_path); monkeypatch.setenv("MFL_CONFIGURATION_EXPORT_TRUST", str(trust))
    service = ConfigurationExportService(ROOT, tmp_path / "receipts", encryption_key="0123456789abcdef")
    manifest = service.build(tenant_id="fictional-tenant")
    serialized = json.dumps(manifest, sort_keys=True)
    assert manifest["privacy"]["private_record_content_included"] is False
    assert manifest["delivery"]["network_used"] is False
    assert "fictional-tenant" in serialized and str(tmp_path) not in serialized
    signature = base64.b64encode(private.sign(signed_payload(manifest))).decode("ascii")
    verified = service.verify_and_receipt(manifest=manifest, tenant_id="fictional-tenant", signature={"key_id": "fictional_key_001", "signature": signature})
    assert verified["manifest"]["signature"]["status"] == "verified"
    encrypted = next((tmp_path / "receipts").glob("*.json.enc"))
    assert b"fictional-tenant" not in encrypted.read_bytes()


def test_pass168_production_admin_route_fails_closed_for_untrusted_signature_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_CONFIGURATION_EXPORT_ROOT", str(tmp_path / "receipts"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.get("/api/admin/configuration-export", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "d" * 32}
    manifest = client.get("/api/admin/configuration-export", headers=headers)
    assert manifest.status_code == 200, manifest.text
    checked = client.post("/api/admin/configuration-export/verify", headers={**headers, "X-MFLL-Idempotency-Key": "configuration-export-verify-001"}, json={"manifest": manifest.json(), "signature": {"key_id": "untrusted_key", "signature": "aW52YWxpZA=="}})
    assert checked.status_code == 200 and checked.json()["manifest"]["signature"]["status"] == "blocked"
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "configuration-export" in (ROOT / relative).read_text(encoding="utf-8")
