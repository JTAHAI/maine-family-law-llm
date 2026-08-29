from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.signed_policy_pack_lifecycle import SignedPolicyPackStore, signable_payload


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {"local_only": True, "review_required": True, "filing_gate_required": True, "no_unapproved_external_provider": True, "no_cross_matter_access": True}


def _trust_config(tmp_path: Path) -> tuple[Path, Ed25519PrivateKey]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    path = tmp_path / "policy-pack-trust.json"
    path.write_text(json.dumps({"schema_version": "policy_pack_trust_v1", "trusted_keys": {"fictional_key_001": base64.b64encode(public).decode("ascii")}}), encoding="utf-8")
    return path, private


def _approve(store: SignedPolicyPackStore, private: Ed25519PrivateKey, *, tenant_id: str, pack_id: str) -> dict:
    drafted = store.draft(tenant_id=tenant_id, pack_id=pack_id, version="1.0.0", controls=CONTROLS)
    assert store.validate(tenant_id=tenant_id, pack_id=pack_id)["policy_pack"]["validation"]["status"] == "valid"
    signature = base64.b64encode(private.sign(signable_payload(drafted["policy_pack"]))).decode("ascii")
    approved = store.approve(tenant_id=tenant_id, pack_id=pack_id, signature={"key_id": "fictional_key_001", "signature": signature})
    assert approved["policy_pack"]["signature"]["status"] == "verified"
    return approved


def test_pass164_signed_lifecycle_validates_activates_diffs_and_rolls_back_encrypted(tmp_path: Path, monkeypatch) -> None:
    trust, private = _trust_config(tmp_path)
    monkeypatch.setenv("MFL_POLICY_PACK_TRUST_CONFIG", str(trust))
    store = SignedPolicyPackStore(tmp_path / "state", encryption_key="0123456789abcdef", project_root=ROOT)
    first = _approve(store, private, tenant_id="fictional-tenant", pack_id="pack_one_001")
    assert store.activate(tenant_id="fictional-tenant", pack_id="pack_one_001")["status"] == "active"
    second = _approve(store, private, tenant_id="fictional-tenant", pack_id="pack_two_001")
    assert second["policy_pack"]["parent_pack_hash"] == first["policy_pack"]["content_sha256"]
    assert store.activate(tenant_id="fictional-tenant", pack_id="pack_two_001")["status"] == "active"
    diff = store.diff(tenant_id="fictional-tenant", pack_id="pack_two_001")
    assert diff["base"]["found"] is True and diff["review_required"] is True
    rolled_back = store.rollback(tenant_id="fictional-tenant", pack_id="pack_two_001")
    assert rolled_back["status"] == "rolled_back"
    encrypted = next((tmp_path / "state").glob("*.json.enc"))
    assert b"pack_one_001" not in encrypted.read_bytes()
    assert b"fictional-tenant" not in encrypted.read_bytes()
    cross_tenant = SignedPolicyPackStore(tmp_path / "state", encryption_key="0123456789abcdef", project_root=ROOT)
    try:
        cross_tenant.validate(tenant_id="other-tenant", pack_id="pack_one_001")
    except ValueError as exc:
        assert str(exc) == "signed_policy_pack_not_found"
    else:
        raise AssertionError("cross-tenant policy-pack access was not refused")


def test_pass164_fails_closed_for_untrusted_signature_and_production_ui_route(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_SIGNED_POLICY_PACK_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    payload = {"pack_id": "pack_ui_001", "version": "1.0.0", "controls": CONTROLS}
    denied = client.post("/api/admin/policy-packs/draft", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}, json=payload)
    assert denied.status_code == 403
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "e" * 32, "X-MFLL-Idempotency-Key": "signed-policy-draft-001"}
    drafted = client.post("/api/admin/policy-packs/draft", headers=headers, json=payload)
    assert drafted.status_code == 200, drafted.text
    validated = client.post("/api/admin/policy-packs/pack_ui_001/validate", headers={**headers, "X-MFLL-Idempotency-Key": "signed-policy-validate-001"})
    assert validated.status_code == 200
    approval = client.post("/api/admin/policy-packs/pack_ui_001/approve", headers={**headers, "X-MFLL-Idempotency-Key": "signed-policy-approve-001"}, json={"signature": {"key_id": "untrusted_key", "signature": "aW52YWxpZA=="}})
    assert approval.status_code == 200 and approval.json()["status"] == "blocked"
    activation = client.post("/api/admin/policy-packs/pack_ui_001/activate", headers={**headers, "X-MFLL-Idempotency-Key": "signed-policy-activate-001"})
    assert activation.status_code == 200 and activation.json()["status"] == "blocked"
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "signed-policy-pack" in (ROOT / relative).read_text(encoding="utf-8")
