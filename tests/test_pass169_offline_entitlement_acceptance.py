from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.offline_entitlement import OfflineEntitlementService, signed_payload


ROOT = Path(__file__).resolve().parents[1]


def _commercial_trust(tmp_path: Path) -> tuple[Path, Ed25519PrivateKey]:
    private = Ed25519PrivateKey.generate(); public = private.public_key().public_bytes_raw()
    path = tmp_path / "entitlement-trust.json"; path.write_text(json.dumps({"schema_version": "offline_entitlement_trust_v1", "commercial_mode": True, "trusted_keys": {"fictional_key_001": base64.b64encode(public).decode("ascii")}}), encoding="utf-8")
    return path, private


def test_pass169_foss_is_inert_and_commercial_entitlement_is_offline_signed_and_encrypted(tmp_path: Path, monkeypatch) -> None:
    service = OfflineEntitlementService(tmp_path / "state", encryption_key="0123456789abcdef", project_root=ROOT)
    assert service.status(tenant_id="fictional-tenant")["status"] == "foss_no_entitlement_required"
    trust, private = _commercial_trust(tmp_path); monkeypatch.setenv("MFL_OFFLINE_ENTITLEMENT_TRUST", str(trust))
    entitlement = {"schema_version": "offline_entitlement_v1", "entitlement_id": "entitlement_001", "subject_ref": "organization_001", "expires_at": "2030-01-01T00:00:00Z", "feature_tiers": ["enterprise"], "telemetry_allowed": False, "key_id": "fictional_key_001"}
    entitlement["signature"] = base64.b64encode(private.sign(signed_payload(entitlement))).decode("ascii")
    verified = service.verify_and_store(tenant_id="fictional-tenant", entitlement=entitlement)
    assert verified["status"] == "active"
    assert verified["boundaries"]["telemetry_used"] is False and verified["boundaries"]["matter_access_decision"] == "never"
    encrypted = next((tmp_path / "state").glob("*.json.enc"))
    assert b"organization_001" not in encrypted.read_bytes()


def test_pass169_production_route_requires_admin_and_foss_mode_stays_unlicensed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_OFFLINE_ENTITLEMENT_ROOT", str(tmp_path / "state")); monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.get("/api/admin/offline-entitlement", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "e" * 32}
    status = client.get("/api/admin/offline-entitlement", headers=headers)
    assert status.status_code == 200 and status.json()["status"] == "foss_no_entitlement_required"
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "offline-entitlement" in (ROOT / relative).read_text(encoding="utf-8")
