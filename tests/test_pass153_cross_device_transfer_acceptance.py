from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.cross_device_transfer import CrossDeviceTransferStore
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "a" * 48}


def test_pass153_creates_encrypted_user_carried_bundle_and_isolated_import(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-transfer-matter"; matter.mkdir()
    (matter / "record.txt").write_text("fictional transfer record", encoding="utf-8")
    transfer_root = tmp_path / "user-carried-transfer-root"
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-transfer-key")
    monkeypatch.setenv("MFL_TRANSFER_ROOT", str(transfer_root))
    store = CrossDeviceTransferStore(matter)
    created = store.create_bundle(transfer_id="transfer_001", passphrase="fictional-transfer-passphrase", actor_role="reviewer", tenant_id="fictional-tenant")
    assert created["user_carried"] is True and created["network_used"] is False
    encrypted = next((transfer_root / "bundles").glob("*.enc")).read_bytes()
    assert b"fictional transfer record" not in encrypted
    listed = store.list_bundles()
    assert listed["paths_disclosed"] is False and listed["bundles"][0]["transfer_id"] == "transfer_001"
    imported = store.import_bundle(transfer_id="transfer_001", passphrase="fictional-transfer-passphrase", actor_role="reviewer", tenant_id="fictional-tenant")
    assert imported["live_matter_overwritten"] is False and imported["active_matter_changed"] is False
    assert (transfer_root / "recovery" / "transfer_001" / "record.txt").read_text(encoding="utf-8") == "fictional transfer record"


def test_pass153_canonical_route_ui_and_inventory(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-api-transfer-matter"; matter.mkdir(); (matter / "record.txt").write_text("fictional api transfer", encoding="utf-8")
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-transfer-key")
    monkeypatch.setenv("MFL_TRANSFER_ROOT", str(tmp_path / "user-carried-transfer-root"))
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(production_app)
    exported = client.post("/api/runtime/cross-device-transfer/export", headers={**_headers(), "X-MFLL-Idempotency-Key": "transfer-fixture-0001"}, json={"transfer_id": "transfer_001", "passphrase": "fictional-transfer-passphrase", "confirmed": True})
    assert exported.status_code == 200 and exported.json()["network_used"] is False
    listed = client.get("/api/runtime/cross-device-transfer", headers=_headers())
    assert listed.status_code == 200 and listed.json()["bundles"][0]["encrypted"] is True
    imported = client.post("/api/runtime/cross-device-transfer/import", headers={**_headers(), "X-MFLL-Idempotency-Key": "transfer-fixture-0002"}, json={"transfer_id": "transfer_001", "passphrase": "fictional-transfer-passphrase", "confirmed": True})
    assert imported.status_code == 200 and imported.json()["active_matter_changed"] is False
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        assert 'id="cross-device-transfer-export"' in (root / relative / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/cross-device-transfer/export" in (root / relative / "workbench.js").read_text(encoding="utf-8")
    registered = {(method, str(route.path)) for route in production_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
