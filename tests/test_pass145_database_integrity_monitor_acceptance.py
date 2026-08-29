from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.database_integrity import (
    DatabaseIntegrityError,
    DatabaseIntegrityReceiptStore,
    run_database_integrity_check,
)
from maine_family_law_llm import api
from maine_family_law_llm.runtime_kernel import DurableJobKernel


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "c" * 48,
    }


def test_pass145_readonly_monitor_detects_corruption_without_disclosing_path(tmp_path: Path) -> None:
    database = tmp_path / "fictional-runtime.sqlite3"
    kernel = DurableJobKernel(database)
    kernel.create_job("fictional_ocr", {"private": "fictional record text"}, matter_id="fictional-matter")
    report = run_database_integrity_check(database)

    assert report["status"] == "pass"
    assert report["database_path_disclosed"] is False
    assert report["database_content_read"] is False
    assert report["destructive_repair_attempted"] is False
    assert report["network_used"] is False
    assert str(database) not in str(report)
    assert "fictional record text" not in str(report)
    assert {row["check_id"] for row in report["checks"]} >= {"sqlite_quick_check", "foreign_key_check"}

    corrupted = tmp_path / "corrupted-runtime.sqlite3"
    corrupted.write_bytes(b"not a sqlite database")
    blocked = run_database_integrity_check(corrupted)
    assert blocked["status"] == "blocked"
    assert blocked["destructive_repair_attempted"] is False
    assert blocked["checks"][0]["error_code"] == "runtime_database_integrity_failed"
    assert any("preserve the original" in row for row in blocked["recovery_guidance"])


def test_pass145_receipt_is_encrypted_hash_linked_and_tenant_bound(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    database = tmp_path / "runtime.sqlite3"
    DurableJobKernel(database)
    report = run_database_integrity_check(database)
    store = DatabaseIntegrityReceiptStore(matter, encryption_key="fictional-db-integrity-key")
    first = store.record(report, actor_role="reviewer", tenant_id="fictional-tenant")
    second = store.record(report, actor_role="reviewer", tenant_id="fictional-tenant")

    assert first["audit_receipt"]["check_id"] != second["audit_receipt"]["check_id"]
    assert store.verify() == {"status": "pass", "receipt_count": 2, "audit_chain_valid": True, "review_required": True}
    assert str(matter).encode("utf-8") not in store.path.read_bytes()
    with pytest.raises(DatabaseIntegrityError, match="tenant_mismatch"):
        store.record(report, actor_role="reviewer", tenant_id="different-fictional-tenant")
    with pytest.raises(DatabaseIntegrityError, match="private_path_refused"):
        store.record({**report, "private": r"C:\fictional\record.sqlite3"}, actor_role="reviewer", tenant_id="fictional-tenant")


def test_pass145_canonical_route_is_active_matter_scoped_and_shipped_in_ui(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    database = tmp_path / "runtime.sqlite3"
    kernel = DurableJobKernel(database)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-db-integrity-key")
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    monkeypatch.setattr(api, "get_runtime_kernel", lambda: kernel)

    client = TestClient(api.app)
    response = client.get("/api/runtime/database-integrity", headers=_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["database_path_disclosed"] is False
    assert payload["destructive_repair_attempted"] is False
    assert payload["audit_receipt"]["check_id"].startswith("dbcheck_")
    assert str(database) not in response.text

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    no_matter = client.get("/api/runtime/database-integrity", headers=_headers())
    assert no_matter.status_code == 409
    assert no_matter.json()["detail"] == "no_active_matter"
    denied = client.get("/api/runtime/database-integrity", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "dashboard_session_required"

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        directory = root / relative
        assert 'id="database-integrity-refresh"' in (directory / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/database-integrity" in (directory / "workbench.js").read_text(encoding="utf-8")


def test_pass145_health_redacts_runtime_database_path_and_production_inventory_registers_route(tmp_path: Path) -> None:
    health = DurableJobKernel(tmp_path / "private-runtime.sqlite3").health()
    assert health["database_path_disclosed"] is False
    assert "database_path" not in health
    registered = {
        (method, str(getattr(route, "path", "")))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    report = EndpointInventory().compare_to_registered(registered, surface="production")
    assert report["status"] == "pass", report
    assert ("GET", "/api/runtime/database-integrity") in registered
