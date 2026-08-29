from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.jurisdiction.packs import FictionalSecondStateReferencePack, JurisdictionPackCatalog, JurisdictionPackError, JurisdictionPackSelectionStore


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_pass192_fictional_second_state_pack_is_signed_and_explicitly_non_selectable(tmp_path: Path) -> None:
    root = tmp_path / "external-jurisdiction-packs"
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    _write_json(root / "jurisdiction_pack_trust.json", {"schema_version": "jurisdiction_pack_trust_v1", "trusted_keys": {"reference-key": public}})
    reference = FictionalSecondStateReferencePack.build(private_key=key, key_id="reference-key")
    _write_json(root / "packs" / "aurora_reference.json", reference)
    catalog = JurisdictionPackCatalog(root, project_root=Path(__file__).resolve().parents[1])
    report = catalog.get_verified("aurora_reference").as_dict()
    assert report["status"] == "reference_verified_not_selectable", report
    assert report["jurisdiction"] == "XX-AURORA"
    assert report["reference_only"] is True
    assert report["signature_verified"] is True
    store = JurisdictionPackSelectionStore(tmp_path / "state", encryption_key="pass192-test-key")
    with pytest.raises(JurisdictionPackError, match="jurisdiction_pack_reference_only_not_selectable"):
        store.select(tenant_id="tenant_alpha", matter_id="fictional_matter_001", pack=catalog.get_verified("aurora_reference"), actor_role="reviewer")


def test_pass192_reference_pack_is_visible_to_the_existing_production_catalog_but_cannot_activate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.production import app

    root = tmp_path / "external-jurisdiction-packs"
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    _write_json(root / "jurisdiction_pack_trust.json", {"schema_version": "jurisdiction_pack_trust_v1", "trusted_keys": {"reference-key": public}})
    _write_json(root / "packs" / "aurora_reference.json", FictionalSecondStateReferencePack.build(private_key=key, key_id="reference-key"))
    monkeypatch.setenv("MFL_JURISDICTION_PACK_ROOT", str(root))
    monkeypatch.setenv("MFL_JURISDICTION_PACK_STATE_ROOT", str(tmp_path / "state"))
    client = TestClient(app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"}
    listed = client.get("/api/jurisdiction-packs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["packs"][0]["reference_only"] is True
    rejected = client.post("/api/jurisdiction-packs/aurora_reference/activate", headers=headers, json={"matter_id": "fictional_matter_001"})
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "jurisdiction_pack_reference_only_not_selectable"
