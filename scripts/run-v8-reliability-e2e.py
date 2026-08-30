"""Exercise local reliability and recovery controls through the frozen r6 runtime.

All observations use a disposable fictional matter.  This runner retains only
safe statuses/counts/hashes in evidence: no prompts, records, filesystem paths,
capabilities, raw diagnostics, or machine identifiers are emitted.  Synthetic
fault and recovery exercises never certify a physical fault, user workload,
performance target, Store qualification, or Enterprise GA.
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


def _header(headers: dict[str, str], name: str) -> str:
    wanted = name.casefold()
    return next((str(value) for key, value in headers.items() if str(key).casefold() == wanted), "")


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    procedure = _module(PROCEDURE_RUNNER, "mfl_v8_procedure_e2e")
    privacy = _module(PRIVACY_RUNNER, "mfl_v8_privacy_e2e")
    shared = procedure._shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_reliability_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_and_production_ui",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This is a bounded local reliability/recovery exercise. Synthetic checks do not establish physical "
            "power-loss resilience, actual user performance, a release metric, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-reliability-") as temporary:
        root = Path(temporary)
        matter, other_matter = root / "fictional-matter", root / "other-fictional-matter"
        matter.mkdir(); other_matter.mkdir(); helper.build_case_fixture(matter)
        process = None
        monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            html_status, html = procedure._text(base_url, "/")
            js_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            telemetry_initial_status, telemetry_initial, _ = privacy._request_result(helper, "GET", base_url, "/api/security/privacy/telemetry")
            telemetry_enable_status, telemetry_enabled, _ = privacy._request_result(helper, "POST", base_url, "/api/security/privacy/telemetry", {"mode": "local_metrics", "approved": True})
            telemetry_disable_status, telemetry_disabled, _ = privacy._request_result(helper, "POST", base_url, "/api/security/privacy/telemetry", {"mode": "off", "approved": True})
            dashboard_status, dashboard, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/health-dashboard")
            journal_status, journal, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/job-journal")
            idempotency_status, idempotency, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/idempotency-status")
            database_status, database, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/database-integrity")
            storage_status, storage, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/storage-pressure")
            clock_status, clock, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/clock-skew")
            performance_catalog_status, performance_catalog, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/performance-gates")

            retry_headers = {"X-MFLL-Idempotency-Key": "fictional-reliability-performance-0001"}
            performance_payload = {"observations": {"launch_ms": 1200, "search_ms": 500}, "evidence_kind": "synthetic_local_test"}
            performance_one_status, performance_one, performance_one_headers = privacy._request_result(helper, "POST", base_url, "/api/runtime/performance-gates", performance_payload, headers=retry_headers)
            performance_two_status, performance_two, performance_two_headers = privacy._request_result(helper, "POST", base_url, "/api/runtime/performance-gates", performance_payload, headers=retry_headers)

            power_headers = {"X-User-Role": "admin", "X-MFLL-Idempotency-Key": "fictional-reliability-power-0001"}
            power_status, power, _ = privacy._request_result(helper, "POST", base_url, "/api/runtime/power-loss-drill", {}, headers=power_headers)
            replay_catalog_status, replay_catalog, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/failure-replay")
            replay_status, replay, _ = privacy._request_result(helper, "POST", base_url, "/api/runtime/failure-replay", {"scenario_id": "authority_not_found", "confirmed": True}, headers={"X-MFLL-Idempotency-Key": "fictional-reliability-replay-0001"})
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            post_switch_journal_status, _, _ = privacy._request_result(helper, "GET", base_url, "/api/runtime/job-journal")
            network = monitor.stop(); monitor = None

            dashboard_components = list(dashboard.get("components") or [])
            checks = {
                "runtime_health_and_fictional_matter_activation": health.get("status") == "ok" and activation.get("status") == "ok",
                "production_reliability_ui_entries_shipped": html_status == 200 and js_status == 200 and all(marker in html for marker in ("telemetry-preference-title", "local-health-dashboard-refresh", "runtime-job-journal-refresh", "database-integrity-refresh", "power-loss-resilience-run", "storage-pressure-refresh", "clock-skew-refresh", "performance-gates-save", "failure-replay-run")) and all(marker in workbench_js for marker in ("/api/security/privacy/telemetry", "/api/runtime/health-dashboard", "/api/runtime/job-journal", "/api/runtime/idempotency-status", "/api/runtime/database-integrity", "/api/runtime/power-loss-drill", "/api/runtime/storage-pressure", "/api/runtime/clock-skew", "/api/runtime/performance-gates", "/api/runtime/failure-replay")),
                "telemetry_is_explicit_local_only_and_reversible": telemetry_initial_status == 200 and (telemetry_initial.get("preference") or {}).get("mode") == "off" and telemetry_enable_status == 200 and (telemetry_enabled.get("preference") or {}).get("mode") == "local_metrics" and telemetry_enabled.get("local_only") is True and telemetry_enabled.get("review_required") is True and telemetry_disable_status == 200 and (telemetry_disabled.get("preference") or {}).get("mode") == "off",
                "content_free_dependency_dashboard_and_job_journal": dashboard_status == 200 and dashboard.get("network_used") is False and dashboard.get("private_paths_included") is False and dashboard.get("private_record_content_included") is False and len(dashboard_components) == 9 and journal_status == 200 and journal.get("matter_scope") == "active_matter_only" and journal.get("job_inputs_exposed") is False and journal.get("job_results_exposed") is False,
                "idempotency_status_is_visible_and_exact_retry_replays": idempotency_status == 200 and idempotency.get("network_used") is False and performance_one_status == 200 and performance_two_status == 200 and _header(performance_one_headers, "X-MFLL-Idempotency-Status") == "recorded" and _header(performance_two_headers, "X-MFLL-Idempotency-Status") == "replayed" and performance_one == performance_two,
                "database_integrity_and_capacity_clock_checks_are_local_and_non_destructive": database_status == 200 and database.get("database_path_disclosed") is False and database.get("database_content_read") is False and database.get("destructive_repair_attempted") is False and storage_status == 200 and (storage.get("write_gate") or {}).get("enforced_by") == "durable_local_write_boundary" and clock_status == 200 and clock.get("timestamps_rewritten") is False and clock.get("network_time_checked") is False,
                "synthetic_power_loss_replay_and_performance_remain_nonrelease": power_status == 200 and power.get("status") == "pass" and power.get("simulation_only") is True and power.get("physical_power_cut_verified") is False and replay_catalog_status == 200 and replay_catalog.get("raw_failures_accepted") is False and replay_status == 200 and replay.get("simulation_only") is True and replay.get("original_operation_reexecuted") is False and performance_catalog_status == 200 and performance_catalog.get("release_evidence_claimed") is False and performance_one.get("release_eligible") is False,
                "active_matter_switch_preserves_isolated_runtime_receipt_boundary": switched.get("status") == "ok" and post_switch_journal_status == 200,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
                "dashboard_component_count": len(dashboard_components),
                "journal_job_count": int((journal.get("counts") or {}).get("total") or 0),
                "power_loss_operation_count": int(power.get("operation_count") or 0),
                "failure_replay_status": str(replay.get("status") or ""),
                "performance_review_status": str(performance_one.get("status") or ""),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"reliability_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
