from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.health_dashboard import (
    HealthDashboardError,
    HealthDependencyDashboardStore,
    collect_dashboard,
)
from maine_family_law_llm import api


class _FictionalKernel:
    def list_jobs(self, *, matter_id: str, limit: int) -> list[dict[str, str]]:
        assert matter_id
        assert limit <= 500
        return [
            {"job_type": "local_ocr", "status": "completed"},
            {"job_type": "model_review", "status": "running"},
        ]


def _dashboard(matter: Path) -> dict:
    return collect_dashboard(
        case_root=matter,
        runtime_health=lambda: {"status": "ok", "blockers": []},
        authority_status=lambda: {
            "status": "pass",
            "active": True,
            "build_id": "fictional-authority-build",
            "retrieval_document_count": 3,
            "freshness_counts": {"current": 3},
        },
        ocr_status=lambda: {
            "status": "ready",
            "one_click_available": False,
            "engine": {"available": True, "pdf_ocr_available": True},
        },
        backup_status=lambda: {
            "status": "ready",
            "backup_root_configured": True,
            "restore_mode": "isolated_rehearsal_only",
            "blockers": [],
        },
        runtime_kernel=_FictionalKernel(),
        matter_id="fictional-matter-scope",
    )


def test_health_dashboard_is_local_content_free_and_hash_linked(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    dashboard = _dashboard(matter)
    assert {row["component_id"] for row in dashboard["components"]} == {
        "api", "database", "authority", "model", "ocr", "media", "storage", "backup", "clock"
    }
    assert dashboard["network_used"] is False
    assert dashboard["private_paths_included"] is False
    assert dashboard["private_record_content_included"] is False
    assert str(matter) not in str(dashboard)

    store = HealthDependencyDashboardStore(matter, encryption_key="fictional-health-dashboard-key")
    first = store.record(dashboard, actor_role="reviewer", tenant_id="fictional-tenant")
    second = store.record(dashboard, actor_role="reviewer", tenant_id="fictional-tenant")
    assert first["audit_receipt"]["snapshot_id"] != second["audit_receipt"]["snapshot_id"]
    assert store.verify() == {
        "status": "pass",
        "snapshot_count": 2,
        "audit_chain_valid": True,
        "review_required": True,
    }
    assert str(matter).encode("utf-8") not in store.path.read_bytes()

    with pytest.raises(HealthDashboardError, match="tenant_mismatch"):
        store.record(dashboard, actor_role="reviewer", tenant_id="other-fictional-tenant")

    with pytest.raises(HealthDashboardError, match="private_path_refused"):
        store.record({"components": [{"component_id": "bad", "summary": r"C:\\fictional\\record.pdf"}]}, actor_role="reviewer", tenant_id="fictional")


def test_canonical_dashboard_route_is_active_matter_scoped_and_shipped_in_ui(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-health-dashboard-key")
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    monkeypatch.setattr(api, "runtime_health_snapshot", lambda: {"status": "ok", "blockers": []})
    monkeypatch.setattr(api, "get_runtime_kernel", lambda: _FictionalKernel())
    monkeypatch.setattr(api, "ocr_prerequisite_status", lambda: {"status": "ready", "one_click_available": False, "engine": {"available": True, "pdf_ocr_available": True}})

    class _Authority:
        def status(self) -> dict:
            return {"status": "pass", "active": True, "build_id": "fictional-authority-build", "retrieval_document_count": 3, "freshness_counts": {"current": 3}}

    class _Backup:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def status(self) -> dict:
            return {"status": "ready", "backup_root_configured": True, "restore_mode": "isolated_rehearsal_only", "blockers": []}

    monkeypatch.setattr(api, "AuthorityProductService", _Authority)
    monkeypatch.setattr(api, "MatterBackupRestoreDrill", _Backup)
    client = TestClient(api.app)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "d" * 48,
    }
    response = client.get("/api/runtime/health-dashboard", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["matter_scope"] == "active_matter_only"
    assert payload["review_required"] is True
    assert payload["network_used"] is False
    assert payload["audit_receipt"]["snapshot_id"].startswith("health_")
    assert len(payload["components"]) == 9
    assert str(matter) not in response.text

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    blocked = client.get("/api/runtime/health-dashboard", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "no_active_matter"

    denied = client.get(
        "/api/runtime/health-dashboard",
        headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "dashboard_session_required"

    root = Path(__file__).resolve().parents[1]
    source_api = (root / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    assert '"/api/runtime/health-dashboard"' in source_api
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        directory = root / relative
        html = (directory / "workbench.html").read_text(encoding="utf-8")
        script = (directory / "workbench.js").read_text(encoding="utf-8")
        assert 'id="local-health-dashboard-refresh"' in html
        assert "/api/runtime/health-dashboard" in script
        assert "Check local dependencies" in html


def test_production_gateway_inventory_checks_local_routes_without_weak_aliases() -> None:
    registered = {
        (method, str(getattr(route, "path", "")))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    report = EndpointInventory().compare_to_registered(registered, surface="production")
    assert report["status"] == "pass", report
    assert ("POST", "/api/records/{record_id}/safe-review-copy") in registered
