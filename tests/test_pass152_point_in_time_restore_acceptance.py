from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.productivity import ProductivitySuiteStore
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
        "X-MFLL-Idempotency-Key": "point-in-time-fixture-0001",
    }


def test_pass152_browses_safe_snapshot_metadata_and_recovers_selected_point(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-recovery-matter"
    matter.mkdir()
    record = matter / "record.txt"
    record.write_text("fictional point one", encoding="utf-8")
    backup_root = tmp_path / "external-encrypted-backups"
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-recovery-key")
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(backup_root))
    store = ProductivitySuiteStore(matter)
    store.save_backup_schedule({"schedule_id": "daily_backup", "enabled": True, "retention_count": 4})
    first = store.run_backup({"schedule_id": "daily_backup"})
    record.write_text("fictional point two", encoding="utf-8")
    second = store.run_backup({"schedule_id": "daily_backup"})

    browser = store.list_backups()
    assert browser["paths_disclosed"] is False
    assert browser["private_record_content_included"] is False
    assert {row["snapshot_id"] for row in browser["snapshots"]} == {first["backup_id"], second["backup_id"]}
    selected = next(row for row in browser["snapshots"] if row["snapshot_id"] == first["backup_id"])
    assert selected["restore_eligible"] is True
    assert selected["source_drill_down"]["source_id"] == f"backup_snapshot:{first['backup_id']}"

    recovered = store.restore_backup(first["backup_id"], {"confirmed": True})
    assert recovered["recovery_matter"]["status"] == "isolated_recovery_copy"
    assert recovered["recovery_matter"]["active_matter_changed"] is False
    assert recovered["live_matter_overwritten"] is False
    assert record.read_text(encoding="utf-8") == "fictional point two"
    assert (backup_root / "recovery" / first["backup_id"] / "record.txt").read_text(encoding="utf-8") == "fictional point one"


def test_pass152_canonical_production_api_ui_and_route_inventory(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-api-recovery-matter"
    matter.mkdir()
    (matter / "record.txt").write_text("fictional api recovery", encoding="utf-8")
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-recovery-key")
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(tmp_path / "external-encrypted-backups"))
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "fictional-runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(production_app)
    assert client.post("/api/productivity/backups/schedules", headers=_headers(), json={"schedule_id": "daily_backup", "enabled": True}).status_code == 200
    created = client.post("/api/productivity/backups/run", headers={**_headers(), "X-MFLL-Idempotency-Key": "point-in-time-fixture-0002"}, json={"schedule_id": "daily_backup"})
    assert created.status_code == 200
    snapshots = client.get("/api/productivity/backups", headers=_headers())
    assert snapshots.status_code == 200
    assert snapshots.json()["snapshots"][0]["restore_eligible"] is True

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        html = (root / relative / "workbench.html").read_text(encoding="utf-8")
        javascript = (root / relative / "workbench.js").read_text(encoding="utf-8")
        assert 'id="productivity-backup-list"' in html
        assert 'id="productivity-backup-snapshot"' in html
        assert "/api/productivity/backups" in javascript
        assert "Isolated point-in-time recovery" in javascript
    registered = {
        (method, str(route.path))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
