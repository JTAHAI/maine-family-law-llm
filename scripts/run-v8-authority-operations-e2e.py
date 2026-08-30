"""Exercise frozen authority-operation review routes without changing authority state.

Only existing external authority metadata is read.  The runner creates no
authority update, never acknowledges activation or rollback, records no source
text or local paths, and uses a temporary LocalAppData profile.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _shared() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_response(value: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence to status, identifiers, counts, and declared blockers."""
    return {
        "status": str(value.get("status") or ""),
        "review_required": value.get("review_required") is True,
        "network_used": value.get("network_used") is False,
        "blockers": [str(item)[:160] for item in list(value.get("blockers") or [])[:20]],
        "source_count": len(list(value.get("sources") or [])),
        "build_count": len(list(value.get("builds") or [])),
        "timeline_count": len(list(value.get("timeline") or [])),
        "result_count": len(list(value.get("results") or [])),
    }


def _rows(value: dict[str, Any], *names: str) -> list[dict[str, Any]]:
    for name in names:
        found = value.get(name)
        if isinstance(found, list):
            return [dict(item) for item in found if isinstance(item, dict)]
    return []


def _response_is_review_safe(value: dict[str, Any]) -> bool:
    return (
        str(value.get("status") or "")
        in {"pass", "passed", "needs_review", "blocked", "not_found", "unavailable", "metadata_observed", "lineage_observed"}
        and value.get("review_required") is True
    )


def run(*, runtime: Path, package: Path, authority_root: Path) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_authority_operations_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_read_only_authority_operations",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_root_external_to_repository_and_msix": True,
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This is a read-only authority operations review. It does not refresh a source, activate a build, "
            "determine current law, decide legal effect, prove browser interaction, or establish Store/Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-authority-operations-") as temporary:
        temp_root = Path(temporary)
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(
                runtime,
                port,
                localappdata=temp_root / "localappdata",
                authority_data_root=authority_root,
            )
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            status = shared.request(helper, "GET", base_url, "/api/authority/status")
            builds_payload = shared.request(helper, "GET", base_url, "/api/authority/builds?limit=20")
            builds = _rows(builds_payload, "builds")
            active_build = next(
                (str(row.get("build_id") or "") for row in builds if row.get("active") is True),
                str((status.get("active_build") or {}).get("build_id") or status.get("build_id") or ""),
            )
            sources_payload = shared.request(helper, "GET", base_url, "/api/authority/sources?limit=100")
            sources = _rows(sources_payload, "sources", "items")
            source = next((row for row in sources if str(row.get("source_id") or "")), {})
            source_id = str(source.get("source_id") or "")
            source_detail = shared.request(helper, "GET", base_url, f"/api/authority/sources/{source_id}") if source_id else {}
            source_span = shared.request(helper, "GET", base_url, f"/api/authority/sources/{source_id}/span") if source_id else {}
            lineage = shared.request(helper, "GET", base_url, f"/api/authority/lineage/{source_id}") if source_id else {}
            graph = shared.request(helper, "GET", base_url, f"/api/authority/graph/{source_id}") if source_id else {}
            gaps = shared.request(helper, "GET", base_url, "/api/authority/gaps")
            freshness = shared.request(helper, "GET", base_url, "/api/authority/freshness")
            availability = shared.request(helper, "GET", base_url, "/api/authority/availability")
            rules = shared.request(helper, "GET", base_url, "/api/authority/rules/history")
            parser = shared.request(helper, "GET", base_url, "/api/authority/parser-regression")
            update_report = (
                shared.request(helper, "GET", base_url, f"/api/authority/update-report/{active_build}")
                if active_build
                else {}
            )
            build_diff = (
                shared.request(helper, "GET", base_url, f"/api/authority/builds/{active_build}/diff")
                if active_build
                else {}
            )
            activation = (
                shared.request(
                    helper, "POST", base_url, "/api/authority/activate",
                    {"build_id": active_build, "acknowledged": False},
                )
                if active_build
                else {}
            )
            rollback = (
                shared.request(
                    helper, "POST", base_url, "/api/authority/rollback",
                    {"build_id": active_build, "acknowledged": False},
                )
                if active_build
                else {}
            )
            network = monitor.stop()
            monitor = None
            checks = {
                "runtime_health": health.get("status") == "ok",
                "active_authority_status_pass": str(status.get("status") or "") == "pass",
                "build_inventory_has_active_build": bool(active_build) and bool(builds),
                "source_inventory_and_exact_drilldown": bool(source_id) and _response_is_review_safe(source_detail) and _response_is_review_safe(source_span),
                "immutable_lineage_review": bool(source_id) and _response_is_review_safe(lineage),
                "citation_graph_review": bool(source_id) and _response_is_review_safe(graph),
                "gap_review_available": _response_is_review_safe(gaps),
                "freshness_dashboard_available": _response_is_review_safe(freshness),
                "availability_monitor_available": _response_is_review_safe(availability),
                "rule_history_review_available": _response_is_review_safe(rules),
                "parser_regression_review_available": _response_is_review_safe(parser),
                "build_diff_review_available": bool(active_build) and _response_is_review_safe(build_diff),
                "update_report_review_available": bool(active_build) and _response_is_review_safe(update_report),
                "activation_requires_explicit_acknowledgement": activation.get("status") == "blocked" and "authority_activation_acknowledgement_required" in list(activation.get("blockers") or []),
                "rollback_requires_explicit_acknowledgement": rollback.get("status") == "blocked" and "authority_rollback_acknowledgement_required" in list(rollback.get("blockers") or []),
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "active_build_id": active_build,
                "source_id": source_id,
                "source_hash": str(source.get("source_hash") or ""),
                "build_count": len(builds),
                "source_count": len(sources),
                "responses": {
                    "status": _safe_response(status),
                    "sources": _safe_response(sources_payload),
                    "source_detail": _safe_response(source_detail),
                    "source_span": _safe_response(source_span),
                    "lineage": _safe_response(lineage),
                    "graph": _safe_response(graph),
                    "gaps": _safe_response(gaps),
                    "freshness": _safe_response(freshness),
                    "availability": _safe_response(availability),
                    "rules": _safe_response(rules),
                    "parser": _safe_response(parser),
                    "update_report": _safe_response(update_report),
                    "build_diff": _safe_response(build_diff),
                },
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"authority_operations_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable.resolve(strict=True),
        package=args.package.resolve(strict=True),
        authority_root=args.authority_data_root.resolve(strict=True),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
