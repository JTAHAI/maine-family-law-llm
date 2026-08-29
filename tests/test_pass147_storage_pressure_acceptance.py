from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.storage_pressure import StoragePressureError, StoragePressureReceiptStore, forecast_storage_pressure
from legal.security import durable_io
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "f" * 48}


def test_pass147_forecast_and_durable_write_gate_are_non_destructive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "40_RUNTIME"; runtime.mkdir()
    (runtime / ".synthetic.tmp").write_bytes(b"temporary")
    report = forecast_storage_pressure(tmp_path, anticipated_write_bytes=1024)
    assert report["status"] in {"ready", "degraded"}
    assert report["paths_disclosed"] is False and report["automatic_cleanup_performed"] is False
    assert str(tmp_path) not in str(report)
    candidate = report["cleanup_candidates"]["candidate_categories"][0]
    assert candidate["candidate_kind"] == "orphan_atomic_temporary_file"
    assert candidate["automatic_deletion"] is False and candidate["requires_explicit_review"] is True

    monkeypatch.setattr(durable_io.shutil, "disk_usage", lambda _path: SimpleNamespace(free=durable_io.required_write_reserve_bytes()))
    with pytest.raises(durable_io.DurableIOError, match="storage_reserve_required"):
        durable_io.atomic_write_bytes(tmp_path / "blocked.state", b"one more byte")
    assert not (tmp_path / "blocked.state").exists()


def test_pass147_receipts_are_encrypted_and_tenant_bound(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    report = forecast_storage_pressure(matter, anticipated_write_bytes=1)
    store = StoragePressureReceiptStore(matter, encryption_key="fictional-storage-key")
    store.record(report, actor_role="reviewer", tenant_id="fictional-tenant")
    assert store.verify()["audit_chain_valid"] is True
    assert str(matter).encode() not in store.path.read_bytes()
    with pytest.raises(StoragePressureError, match="tenant_mismatch"):
        store.record(report, actor_role="reviewer", tenant_id="other-tenant")


def test_pass147_canonical_route_ui_and_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-storage-key")
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    response = TestClient(api.app).get("/api/runtime/storage-pressure", headers=_headers())
    assert response.status_code == 200
    assert response.json()["write_gate"]["enforced_by"] == "durable_local_write_boundary"
    assert response.json()["audit_receipt"]["forecast_id"].startswith("storage_")
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        assert 'id="storage-pressure-refresh"' in (root / relative / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/storage-pressure" in (root / relative / "workbench.js").read_text(encoding="utf-8")
    registered = {(method, str(route.path)) for route in production_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
