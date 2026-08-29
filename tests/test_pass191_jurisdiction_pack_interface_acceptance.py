from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.jurisdiction.packs import JurisdictionPackCatalog, JurisdictionPackSelectionStore, signable_payload


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _catalog_fixture(root: Path) -> dict:
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode("ascii")
    _write_json(
        root / "jurisdiction_pack_trust.json",
        {"schema_version": "jurisdiction_pack_trust_v1", "trusted_keys": {"external-pack-key": public_key}},
    )
    pack = {
        "schema_version": "jurisdiction_pack_v1",
        "pack_id": "maine_core",
        "jurisdiction": "US-ME",
        "version": "1.0.0",
        "components": {
            "authority_manifest_sha256": _sha("authority"),
            "citation_profile_sha256": _sha("citation"),
            "forms_catalog_sha256": _sha("forms"),
            "procedure_profile_sha256": _sha("procedure"),
            "terminology_profile_sha256": _sha("terminology"),
            "safety_policy_sha256": _sha("safety"),
            "index_snapshot_sha256": _sha("index"),
        },
        "controls": {
            "local_only": True,
            "review_required": True,
            "safety_policy_required": True,
            "jurisdiction_decision_prohibited": True,
        },
    }
    pack["signature"] = {
        "key_id": "external-pack-key",
        "signature": base64.b64encode(private_key.sign(signable_payload(pack))).decode("ascii"),
    }
    _write_json(root / "packs" / "maine_core.json", pack)
    return pack


def test_pass191_verifies_external_component_boundary_and_encrypted_matter_selection(tmp_path: Path) -> None:
    root = tmp_path / "external-packs"
    _catalog_fixture(root)
    catalog = JurisdictionPackCatalog(root, project_root=Path(__file__).resolve().parents[1])
    pack = catalog.get_verified("maine_core")
    assert pack.status == "verified", pack.as_dict()
    assert pack.signature_verified is True
    assert set(pack.component_hashes) == {
        "authority_manifest_sha256", "citation_profile_sha256", "forms_catalog_sha256", "procedure_profile_sha256",
        "terminology_profile_sha256", "safety_policy_sha256", "index_snapshot_sha256",
    }
    store_root = tmp_path / "encrypted-state"
    store = JurisdictionPackSelectionStore(store_root, encryption_key="pass191-test-key")
    selected = store.select(tenant_id="tenant_alpha", matter_id="fictional_matter_001", pack=pack, actor_role="reviewer")
    assert selected["status"] == "selected_review_required"
    assert selected["selection"]["jurisdiction"] == "US-ME"
    assert selected["jurisdiction_decision_prohibited"] is True
    assert store.status(tenant_id="tenant_beta", matter_id="fictional_matter_001")["status"] == "not_selected"
    raw = next(store_root.glob("*.json.enc")).read_text(encoding="utf-8")
    assert "fictional_matter_001" not in raw


def test_pass191_unsigned_or_weakened_pack_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "external-packs"
    pack = _catalog_fixture(root)
    pack["controls"]["local_only"] = False
    _write_json(root / "packs" / "maine_core.json", pack)
    report = JurisdictionPackCatalog(root, project_root=Path(__file__).resolve().parents[1]).get_verified("maine_core").as_dict()
    assert report["status"] == "blocked"
    assert "jurisdiction_pack_control_required:local_only" in report["blockers"]
    assert "jurisdiction_pack_signature_invalid" in report["blockers"]


def test_pass191_production_routes_enforce_tenant_scope_and_keep_paths_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.contracts import EndpointInventory
    from app.api.production import app

    root = tmp_path / "external-packs"
    _catalog_fixture(root)
    monkeypatch.setenv("MFL_JURISDICTION_PACK_ROOT", str(root))
    monkeypatch.setenv("MFL_JURISDICTION_PACK_STATE_ROOT", str(tmp_path / "selection-state"))
    client = TestClient(app)
    denied = client.get("/api/jurisdiction-packs", headers={"X-User-Role": "reviewer"})
    assert denied.status_code == 403
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"}
    listed = client.get("/api/jurisdiction-packs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["packs"][0]["status"] == "verified"
    activated = client.post("/api/jurisdiction-packs/maine_core/activate", headers=headers, json={"matter_id": "fictional_matter_001"})
    assert activated.status_code == 200
    payload = activated.json()
    assert payload["status"] == "selected_review_required"
    assert payload["matter_scope"] == "tenant_scoped_matter_selection"
    assert str(tmp_path) not in json.dumps(payload)
    cross_tenant = client.get("/api/jurisdiction-packs/matters/fictional_matter_001", headers={**headers, "X-Tenant-Id": "other_tenant"})
    assert cross_tenant.status_code == 200
    assert cross_tenant.json()["status"] == "not_selected"
    registered = {
        (method, str(route.path)) for route in app.routes for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
    root_path = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root_path / relative).read_text(encoding="utf-8")
        assert "jurisdiction-pack-control" in text
        assert "/api/jurisdiction-packs" in text
