"""Exercise a fictional review-only deadline dependency graph in the frozen runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _shared() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if spec is None or spec.loader is None: raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _status(helper: Any, method: str, base_url: str, route: str) -> int:
    request = urllib.request.Request(f"{base_url}{route}", method=method, headers={**helper.QA_HEADERS, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read(); return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read(); return int(exc.code)


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    shared = _shared(); shared.validate_runtime_pair(runtime, package); helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_deadline_dependency_e2e_v1", "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True, "execution_level": "frozen_runtime_canonical_api",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime), "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This is a local review candidate from fictional inputs. It does not establish an actual court deadline, authority freshness, service, timeliness, legal effect, filing readiness, or GA status.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-deadline-dependency-") as temporary:
        root = Path(temporary); matter, other = root / "fictional-matter", root / "fictional-other-matter"
        matter.mkdir(); other.mkdir(); records = helper.build_case_fixture(matter)
        record = next(row for row in records if row.get("evidence_id") == "REC-DOCX"); record_hash = str(record.get("source_hash") or "")
        process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            shared.request(helper, "POST", base_url, "/api/calendar/events", {"events": [{"event_id": "trigger_001", "kind": "completed_service_candidate", "date_time": "2026-01-02T12:00:00", "time_zone": "America/New_York", "document_or_notice": "Fictional review trigger", "person_or_role": "fictional role", "method": "unknown", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash, "page": 1}}]})
            shared.request(helper, "POST", base_url, "/api/calendar/rules", {"rules": [{"rule_id": "fictional_rule_001", "citation": "Fictional review rule", "freshness": "unknown", "triggering_event": "completed_service_candidate", "unit": "days", "count": 7, "inclusion_rule": "review required", "weekend_holiday_handling": "unknown", "source_ref": {"record_id": "fictional_rule_source", "source_hash": "b" * 64, "page": 1}, "jurisdiction": "Maine"}]})
            first = shared.request(helper, "POST", base_url, "/api/calendar/deadline-dependencies", {"dependency_id": "fictional_deadline_001", "rule_id": "fictional_rule_001", "trigger_event_id": "trigger_001", "holidays": [], "user_confirmed": True})
            graph = shared.request(helper, "GET", base_url, "/api/calendar/deadline-dependencies/fictional_deadline_001")
            trigger = shared.request(helper, "GET", base_url, "/api/calendar/deadline-dependencies/fictional_deadline_001/trigger-source")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, "/api/calendar/deadline-dependencies/fictional_deadline_001")
            network = monitor.stop(); monitor = None
            encrypted = list(matter.rglob("calendar.json.enc")); ciphertext = encrypted[0].read_bytes() if len(encrypted) == 1 else b""
            active = dict(graph.get("active_candidate") or {}); trigger_source = dict(trigger.get("source") or {})
            checks = {
                "runtime_health": health.get("status") == "ok", "fictional_matter_activated": activated.get("status") == "ok",
                "candidate_created_review_required_non_filing": bool(first.get("candidate_id")) and first.get("review_required") is True and first.get("filing_ready") is False,
                "candidate_is_explicit_review_only": active.get("review_required") is True and active.get("candidate_result") == "2026-01-09",
                "trigger_hash_bound_to_active_record": str(trigger_source.get("record_id") or "").casefold() == "rec-docx" and str(trigger_source.get("source_hash") or "") == record_hash and bool(trigger_source.get("source_token")),
                "encrypted_dependency_state": len(encrypted) == 1 and b"Fictional review trigger" not in ciphertext,
                "cross_matter_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {"dependency_id": "fictional_deadline_001", "candidate_id": str(first.get("candidate_id") or ""), "candidate_result": str(active.get("candidate_result") or ""), "trigger_source_hash": str(trigger_source.get("source_hash") or ""), "encrypted_state_sha256": hashlib.sha256(ciphertext).hexdigest(), "cross_matter_status": cross_status, "network_samples": int(network.get("sample_count") or 0)}
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed); report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"deadline_dependency_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path); parser.add_argument("--output", required=True, type=Path); args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True)); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
