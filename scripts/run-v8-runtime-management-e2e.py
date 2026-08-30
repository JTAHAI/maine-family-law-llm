"""Exercise safe local runtime-management paths through the frozen r6 runtime.

The model admission boundary remains intentionally fail-closed: this runner
does not invoke, admit, or download a model.  It uses only a disposable
fictional matter and records no prompt, record, or authority text in evidence.
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


def _procedure() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_v8_procedure_e2e", PROCEDURE_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("procedure_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _encrypted(case_root: Path, relative: str, forbidden: str) -> bool:
    path = case_root / relative
    return path.is_file() and forbidden.encode("utf-8") not in path.read_bytes()


def run(*, runtime: Path, package: Path, authority_root: Path) -> dict[str, Any]:
    procedure = _procedure()
    shared = procedure._shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_runtime_management_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This verifies bounded local runtime-management behavior only. No model was downloaded, admitted, "
            "invoked, or promoted; no legal answer, task performance, model quality, hardware capacity, Store "
            "qualification, or Enterprise GA conclusion is established."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-runtime-management-") as temporary:
        root = Path(temporary)
        matter, other_matter = root / "fictional-matter", root / "other-fictional-matter"
        matter.mkdir()
        other_matter.mkdir()
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            ui_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            benchmark = shared.request(helper, "POST", base_url, "/api/runtime/hardware-benchmarks", {"benchmark_id": "fictional_hardware_001", "user_confirmed": True})
            route = shared.request(helper, "POST", base_url, "/api/local-workbench/models/route", {"task": "draft_review"})
            warm = shared.request(helper, "POST", base_url, "/api/runtime/warm-model-pool/warm", {"task": "draft_review", "user_confirmed": True})
            cache = shared.request(helper, "POST", base_url, "/api/runtime/context-cache", {
                "cache_id": "fictional_cache_001", "kind": "retrieval", "scope": "matter",
                "source_refs": [{"source_id": "fictional_record", "content_sha256": "a" * 64, "private_record": True, "source_token": "b" * 64}],
                "artifact": {"summary": "Fictional cache result"},
            })
            invalidated = shared.request(helper, "POST", base_url, "/api/runtime/context-cache/invalidate", {"changes": [{"source_id": "fictional_record", "content_sha256": "c" * 64}]})
            speculative = shared.request(helper, "POST", base_url, "/api/runtime/speculative-retrieval", {"preview_id": "fictional_preview_001", "typed_intent": "Maine family-law review question"})
            discarded = shared.request(helper, "POST", base_url, "/api/runtime/speculative-retrieval/fictional_preview_001/discard", {})
            budget = shared.request(helper, "POST", base_url, "/api/runtime/context-budgets", {
                "budget_id": "fictional_budget_001", "task": "research",
                "source_refs": [{"source_id": "official_statute", "content_sha256": "d" * 64, "char_count": 8000, "lane": "legal_authority"}, {"source_id": "private_record", "content_sha256": "e" * 64, "char_count": 4000, "lane": "private_record"}],
                "verifier_requirements": {"citation": True, "quote": True, "claim": True}, "requested_context_tokens": 99999,
            })
            batch = shared.request(helper, "POST", base_url, "/api/runtime/batch-inference", {
                "batch_id": "fictional_batch_001", "user_confirmed": True,
                "items": [
                    {"item_id": "item_001", "job_kind": "extract", "source_ref": {"source_id": "fictional_record_1", "content_sha256": "f" * 64}, "execution_profile": {"context_budget_id": "fictional_budget_001"}},
                    {"item_id": "item_002", "job_kind": "extract", "source_ref": {"source_id": "fictional_record_2", "content_sha256": "0" * 64}, "execution_profile": {"context_budget_id": "fictional_budget_001"}},
                ],
            })
            first_cancel = shared.request(helper, "POST", base_url, "/api/runtime/batch-inference/fictional_batch_001/items/item_001/cancel", {})
            second_cancel = shared.request(helper, "POST", base_url, "/api/runtime/batch-inference/fictional_batch_001/items/item_002/cancel", {})
            low_enabled = shared.request(helper, "PUT", base_url, "/api/runtime/low-memory-mode", {"active": True, "user_confirmed": True})
            low_disabled = shared.request(helper, "PUT", base_url, "/api/runtime/low-memory-mode", {"active": False, "user_confirmed": True})
            recovery = shared.request(helper, "POST", base_url, "/api/runtime/crash-recovery", {})

            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_statuses = {
                "hardware": procedure._status(helper, base_url, "/api/runtime/hardware-benchmarks/fictional_hardware_001"),
                "cache": procedure._status(helper, base_url, "/api/runtime/context-cache/fictional_cache_001"),
                "preview": procedure._status(helper, base_url, "/api/runtime/speculative-retrieval/fictional_preview_001"),
                "budget": procedure._status(helper, base_url, "/api/runtime/context-budgets/fictional_budget_001"),
                "batch": procedure._status(helper, base_url, "/api/runtime/batch-inference/fictional_batch_001"),
            }
            network = monitor.stop()
            monitor = None
            benchmark_row = dict(benchmark)
            cache_row = dict(cache.get("entry") or {})
            preview = dict(speculative.get("preview") or {})
            discarded_preview = dict(discarded.get("preview") or {})
            budget_row = dict(budget.get("budget") or {})
            batch_row = dict(batch.get("batch") or {})
            second_batch = dict(second_cancel.get("batch") or {})
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "shipped_production_ui_entries_present": ui_status == 200 and all(value in workbench_js for value in (
                    "Hardware benchmark", "/api/runtime/hardware-benchmarks", "Model admission benchmark", "Task-specific local model routing", "Warm model pool", "/api/runtime/warm-model-pool/warm", "Prompt-prefix and retrieval cache", "/api/runtime/context-cache", "Speculative retrieval", "/api/runtime/speculative-retrieval", "Adaptive context budget", "/api/runtime/context-budgets", "Batch inference scheduler", "/api/runtime/batch-inference", "Low-memory mode", "/api/runtime/low-memory-mode", "Runtime crash recovery", "/api/runtime/crash-recovery",
                )),
                "hardware_benchmark_is_local_and_no_model_throughput_claim": benchmark_row.get("network_used") is False and (benchmark_row.get("model_throughput") or {}).get("status") == "not_measured",
                "task_routing_and_warm_pool_refuse_unadmitted_model": str(route.get("admission_boundary") or "") and warm.get("status") == "not_warmed_no_task_admission_review_required",
                "cache_is_review_required_and_invalidates_changed_source": cache_row.get("status") == "valid_review_required" and "fictional_cache_001" in list(invalidated.get("invalidated_cache_ids") or []),
                "speculative_retrieval_never_commits_answer": preview.get("answer_committed") is False and discarded_preview.get("status") == "discarded_review_required" and discarded_preview.get("candidate_sources") == [],
                "context_budget_reserves_verifier_capacity": budget_row.get("review_required") is True and (budget_row.get("allocation") or {}).get("verifier_reserve_tokens") == 1920,
                "batch_is_nonexecuting_and_each_child_cancels": batch_row.get("execution_not_automatic") is True and any(row.get("status") == "cancelled_review_required" for row in list(second_batch.get("items") or [])),
                "low_memory_mode_is_reversible": low_enabled.get("active") is True and (low_enabled.get("fallbacks") or {}).get("retrieval") == "lexical_only" and low_disabled.get("active") is False,
                "crash_recovery_returns_safe_report": isinstance(recovery, dict) and str(recovery.get("matter_scope") or "") == "active_matter_only",
                "encrypted_runtime_sidecars": all((
                    _encrypted(matter, "40_RUNTIME/hardware-benchmarks/benchmarks.json.enc", "fictional_hardware_001"),
                    _encrypted(matter, "40_RUNTIME/warm-model-pool/pool.json.enc", "draft_review"),
                    _encrypted(matter, "40_RUNTIME/context-cache/entries.json.enc", "Fictional cache result"),
                    _encrypted(matter, "40_RUNTIME/speculative-retrieval/previews.json.enc", "Maine family-law"),
                    _encrypted(matter, "40_RUNTIME/context-budgets/budgets.json.enc", "official_statute"),
                    _encrypted(matter, "40_RUNTIME/batch-scheduler/batches.json.enc", "fictional_record_1"),
                    _encrypted(matter, "40_RUNTIME/low-memory-mode/state.json.enc", "low_memory_mode_activated"),
                )),
                "cross_matter_access_denied": switched.get("status") == "ok" and all(value == 404 for value in cross_statuses.values()),
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "cross_matter_statuses": cross_statuses, "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
                "model_route_status": str(route.get("status") or ""), "warm_pool_status": str(warm.get("status") or ""),
                "recovery_status": str(recovery.get("status") or ""),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"runtime_management_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_root.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
