from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.productivity import ProductivitySuiteError, ProductivitySuiteStore
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
        "X-MFLL-Idempotency-Key": "incremental-backup-fixture-0001",
    }


def test_pass151_incremental_chunks_deduplicate_verify_and_restore_independently(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-backup-matter"
    matter.mkdir()
    stable = b"fictional-stable-record-" * 40_000
    (matter / "stable.txt").write_bytes(stable)
    (matter / "changed.txt").write_text("fictional version one", encoding="utf-8")
    backup_root = tmp_path / "external-encrypted-backups"
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-backup-key")
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "fictional-runtime-state"))
    store = ProductivitySuiteStore(matter)
    store.save_backup_schedule({"schedule_id": "daily_backup", "enabled": True, "retention_count": 3})

    first = store.run_backup({"schedule_id": "daily_backup"})
    assert first["backup_format"] == "incremental_encrypted_chunks_v2"
    assert first["verified"] is True and first["restore_independent"] is True
    assert first["new_chunk_count"] == first["chunk_count"]

    (matter / "changed.txt").write_text("fictional version two", encoding="utf-8")
    second = store.run_backup({"schedule_id": "daily_backup"})
    assert second["reused_chunk_count"] > 0
    assert second["new_chunk_count"] < second["chunk_count"]
    verified = store.verify_backup(second["backup_id"])
    assert verified["status"] == "pass" and verified["restore_independent"] is True

    first_manifest = backup_root / f"{first['backup_id']}.json.enc"
    first_manifest.unlink()
    assert store.verify_backup(second["backup_id"])["status"] == "pass"
    restored = store.restore_backup(second["backup_id"], {"confirmed": True})
    assert restored["status"] == "restored_to_separate_recovery_directory"
    assert restored["live_matter_overwritten"] is False and restored["restore_independent"] is True
    recovery = backup_root / "recovery" / second["backup_id"]
    assert (recovery / "stable.txt").read_bytes() == stable
    assert (recovery / "changed.txt").read_text(encoding="utf-8") == "fictional version two"
    assert all(b"fictional-stable-record" not in path.read_bytes() for path in backup_root.rglob("*.enc"))
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(matter / "unsafe-internal-backups"))
    with pytest.raises(ProductivitySuiteError, match="outside_active_matter"):
        store.run_backup({"schedule_id": "daily_backup"})


def test_pass151_preserves_legacy_snapshot_readability_and_production_ui_route(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-legacy-backup-matter"
    matter.mkdir()
    backup_root = tmp_path / "external-encrypted-backups"
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-backup-key")
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "fictional-runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    store = ProductivitySuiteStore(matter)
    legacy_id = "backup_legacy_001"
    raw = b"fictional legacy record"
    package = {
        "schema_version": "encrypted_matter_backup_v1",
        "backup_id": legacy_id,
        "matter_scope": store.scope,
        "files": [{"path": "legacy.txt", "sha256": __import__("hashlib").sha256(raw).hexdigest(), "size": len(raw), "content": base64.b64encode(raw).decode("ascii")}],
        "file_count": 1,
    }
    backup_root.mkdir()
    (backup_root / f"{legacy_id}.json.enc").write_text(json.dumps(store.encryptor.encrypt_json(package)), encoding="utf-8")
    legacy = store.verify_backup(legacy_id)
    assert legacy["status"] == "pass" and legacy["backup_format"] == "legacy_encrypted_snapshot_v1"

    client = TestClient(production_app)
    schedule = client.post("/api/productivity/backups/schedules", headers=_headers(), json={"schedule_id": "daily_backup", "enabled": True, "retention_count": 3})
    assert schedule.status_code == 200
    run = client.post("/api/productivity/backups/run", headers={**_headers(), "X-MFLL-Idempotency-Key": "incremental-backup-fixture-0002"}, json={"schedule_id": "daily_backup"})
    assert run.status_code == 200
    assert run.json()["backup_format"] == "incremental_encrypted_chunks_v2"

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        html = (root / relative / "workbench.html").read_text(encoding="utf-8")
        javascript = (root / relative / "workbench.js").read_text(encoding="utf-8")
        assert "Incremental encrypted backup" in html
        assert "restore_independent" in javascript
        assert "/api/productivity/backups/run" in javascript
