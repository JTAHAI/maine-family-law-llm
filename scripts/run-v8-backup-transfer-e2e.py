"""Exercise backup, isolated recovery, transfer, and migration paths in frozen r6.

Only disposable fictional matter files are used.  Evidence retains safe status,
counts, and hashes—not bundle passphrases, opaque transfer identifiers, backup
locations, file paths, or file content.  This is not a second-device, isolated
Windows-install, WACK, rollback, signing, or Store qualification run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_RUNNER = ROOT / "scripts" / "run-v8-procedure-review-e2e.py"
PRIVACY_RUNNER = ROOT / "scripts" / "run-v8-privacy-security-e2e.py"


def _module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    procedure = _module(PROCEDURE_RUNNER, "mfl_v8_procedure_e2e")
    privacy = _module(PRIVACY_RUNNER, "mfl_v8_privacy_e2e")
    shared = procedure._shared(); shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_backup_transfer_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_and_production_ui",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime),
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": (
            "This verifies local isolated-recovery contracts with a disposable fictional matter only. It does not "
            "prove a second device, removable media durability, a live-package upgrade, WACK, rollback rehearsal, "
            "signing ceremony, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-backup-transfer-") as temporary:
        root = Path(temporary); matter = root / "fictional-matter"; matter.mkdir(); helper.build_case_fixture(matter)
        process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(
                runtime,
                port,
                localappdata=root / "localappdata",
                # This is deliberately outside the fictional active matter,
                # mirroring the explicit user-carried destination required by
                # the production feature.
                transfer_root=root / "user-carried-transfer-root",
            )
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            html_status, html = procedure._text(base_url, "/")
            js_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            schedule_status, schedule, _ = privacy._request_result(helper, "POST", base_url, "/api/productivity/backups/schedules", {"schedule_id": "fictional_daily_backup", "enabled": True, "retention_count": 3}, headers={"X-MFLL-Idempotency-Key": "fictional-backup-schedule-0001"})
            backup_status, backup, _ = privacy._request_result(helper, "POST", base_url, "/api/productivity/backups/run", {"schedule_id": "fictional_daily_backup"}, headers={"X-MFLL-Idempotency-Key": "fictional-backup-run-0001"})
            backup_id = str(backup.get("backup_id") or "")
            snapshots_status, snapshots, _ = privacy._request_result(helper, "GET", base_url, "/api/productivity/backups")
            verify_status, verified, _ = privacy._request_result(helper, "GET", base_url, f"/api/productivity/backups/{backup_id}/verify") if backup_id else (0, {}, {})
            restore_status, restored, _ = privacy._request_result(helper, "POST", base_url, f"/api/productivity/backups/{backup_id}/restore", {"confirmed": True}, headers={"X-MFLL-Idempotency-Key": "fictional-backup-restore-0001"}) if backup_id else (0, {}, {})

            transfer_status, transfer, _ = privacy._request_result(helper, "POST", base_url, "/api/runtime/cross-device-transfer/export", {"transfer_id": "fictional_transfer_001", "passphrase": "fictional-transfer-passphrase", "confirmed": True}, headers={"X-MFLL-Idempotency-Key": "fictional-transfer-export-0001"})
            transfer_list_status, transfer_list, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/cross-device-transfer")
            transfer_import_status, transfer_import, _ = privacy._request_result(helper, "POST", base_url, "/api/runtime/cross-device-transfer/import", {"transfer_id": "fictional_transfer_001", "passphrase": "fictional-transfer-passphrase", "confirmed": True}, headers={"X-MFLL-Idempotency-Key": "fictional-transfer-import-0001"})

            migration_status, migration, _ = privacy._request_result(helper, "POST", base_url, "/api/runtime/schema-migration-lab/run", {"source_schema": "6.0.4.0", "scenario": "interrupt_after_commit", "confirmed": True}, headers={"X-MFLL-Idempotency-Key": "fictional-migration-run-0001"})
            migration_list_status, migration_list, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/schema-migration-lab")
            network = monitor.stop(); monitor = None

            snapshot_rows = list(snapshots.get("snapshots") or [])
            bundle_rows = list(transfer_list.get("bundles") or [])
            migration_rows = list(migration_list.get("runs") or [])
            checks = {
                "runtime_health_and_fictional_matter_activation": health.get("status") == "ok" and activation.get("status") == "ok",
                "production_backup_transfer_migration_ui_entries_shipped": html_status == 200 and js_status == 200 and all(marker in html for marker in ("Incremental encrypted backup", "productivity-backup-list", "productivity-backup-snapshot", "cross-device-transfer-export", "schema-migration-lab-run")) and all(marker in workbench_js for marker in ("/api/productivity/backups/run", "restore_independent", "/api/runtime/cross-device-transfer/export", "/api/runtime/schema-migration-lab/run")),
                "incremental_backup_verifies_and_restores_only_to_isolated_copy": schedule_status == 200 and backup_status == 200 and backup.get("backup_format") == "incremental_encrypted_chunks_v2" and backup.get("verified") is True and backup.get("restore_independent") is True and snapshots_status == 200 and len(snapshot_rows) >= 1 and verify_status == 200 and verified.get("status") == "pass" and verified.get("restore_independent") is True and restore_status == 200 and restored.get("live_matter_overwritten") is False and (restored.get("recovery_matter") or {}).get("active_matter_changed") is False,
                "cross_device_transfer_is_user_carried_encrypted_and_nonmerging": transfer_status == 200 and transfer.get("user_carried") is True and transfer.get("network_used") is False and transfer_list_status == 200 and len(bundle_rows) >= 1 and bool(bundle_rows[0].get("encrypted")) and transfer_import_status == 200 and transfer_import.get("live_matter_overwritten") is False and transfer_import.get("active_matter_changed") is False,
                "schema_migration_lab_is_synthetic_and_preserves_live_matter": migration_status == 200 and migration.get("status") == "pass_review_required" and migration.get("live_matter_changed") is False and migration.get("network_used") is False and (migration.get("source_drill_down") or {}).get("source_type") == "synthetic_migration_contract" and migration_list_status == 200 and len(migration_rows) >= 1 and int(migration_rows[0].get("check_count") or 0) == 1,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            # This deliberately small, hash-only subrecord is the only form
            # of this frozen fictional backup proof accepted by the rollback
            # planner.  It exposes neither the recovery location nor private
            # record data, but binds the recovery result to this exact MSIX.
            recovery_passed = checks["incremental_backup_verifies_and_restores_only_to_isolated_copy"]
            report["status"] = "pass" if recovery_passed else "blocked"
            report["candidate_package_sha256"] = report["package_sha256"]
            report["backup_sha256"] = str(backup.get("encrypted_sha256") or "").casefold()
            report["isolated_recovery_restore"] = "pass" if recovery_passed else "blocked"
            report["active_matter_unchanged"] = bool(
                recovery_passed
                and restored.get("live_matter_overwritten") is False
                and (restored.get("recovery_matter") or {}).get("active_matter_changed") is False
            )
            report["synthetic_data_only"] = True
            report["artifacts"] = {
                "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
                "snapshot_count": len(snapshot_rows), "transfer_bundle_count": len(bundle_rows),
                "migration_run_count": len(migration_rows),
                "backup_format": str(backup.get("backup_format") or ""),
                "migration_status": str(migration.get("status") or ""),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"backup_transfer_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
