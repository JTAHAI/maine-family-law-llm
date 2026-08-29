"""Exercise a durable fictional draft/restart journey through an exact frozen runtime.

This runner never opens a user matter. It creates a disposable fictional corpus,
uses the canonical local document-workspace API, terminates the runtime, starts
the same executable with the same isolated application-data directory, reopens
the fictional corpus, and verifies only hashes, identifiers, status, and audit
integrity in its report.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_HELPER_PATH = ROOT / "scripts" / "run-installed-offline-qualification.py"


def load_helper() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_installed_offline_qualification", QUALIFICATION_HELPER_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("installed_offline_qualification_helper_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_runtime_pair(runtime: Path, package: Path) -> None:
    expected_runtime = package.parent.parent / "runtime" / "MaineFamilyLawLLM.exe"
    if runtime.resolve() != expected_runtime.resolve():
        raise ValueError("runtime_is_not_paired_with_supplied_msix")
    try:
        with zipfile.ZipFile(package) as archive:
            if archive.namelist().count("MaineFamilyLawLLM.exe") != 1:
                raise ValueError("package_executable_missing_or_ambiguous")
            with archive.open("MaineFamilyLawLLM.exe") as stream:
                packaged_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("package_executable_unverifiable") from exc
    if packaged_hash != sha256_file(runtime):
        raise ValueError("runtime_bytes_differ_from_supplied_msix")


def safe_document_state(document: dict[str, Any]) -> dict[str, Any]:
    content = str(document.get("content") or "")
    return {
        "document_id": str(document.get("document_id") or ""),
        "current_revision_id": str(document.get("current_revision_id") or ""),
        "original_revision_id": str(document.get("original_revision_id") or ""),
        "status": str(document.get("status") or ""),
        "review_required": document.get("review_required") is True,
        "original_preserved": document.get("original_preserved") is True,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def request(helper: Any, method: str, base_url: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.request_json(method, f"{base_url}{route}", payload)


def terminate(process: Any) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001
        process.kill()
        process.wait(timeout=30)


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    validate_runtime_pair(runtime, package)
    helper = load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_durable_restart_e2e_v2",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "package_sha256": sha256_file(package),
        "runtime_sha256": sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "execution_level": "frozen_runtime_canonical_api",
        "shutdown_method": "owned_QA_process_termination_not_native_UI_quit",
        "installed_package_tested": False,
        "local_only_zero_network_proven": False,
        "notice": "Fictional software-contract evidence only. It does not establish legal authority, attorney review, a pilot, Store qualification, or Enterprise GA.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-durable-restart-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        helper.build_case_fixture(case_root)
        localappdata = temporary_root / "localappdata"
        process = None
        first_monitor = None
        second_monitor = None
        try:
            first_port = helper.free_port()
            first_base = f"http://127.0.0.1:{first_port}"
            process = helper.start_runtime(runtime, first_port, localappdata=localappdata)
            first_monitor = helper.RuntimeNetworkMonitor(process.pid)
            first_monitor.start()
            health_before = helper.wait_json(f"{first_base}/api/health", timeout_s=180)
            first_bound = helper.verify_runtime_instance(first_base, process.qa_service_instance)
            if not first_bound:
                raise RuntimeError("first_runtime_instance_mismatch")
            activated_before = request(helper, "POST", first_base, "/api/activate-corpus", {"case_root": str(case_root)})
            created = request(
                helper,
                "POST",
                first_base,
                "/api/document-workspace/documents",
                {
                    "title": "Fictional durable review draft",
                    "content": "Fictional draft version one. Review required.",
                    "document_type": "motion",
                },
            )["document"]
            proposal = request(
                helper,
                "POST",
                first_base,
                f"/api/document-workspace/documents/{created['document_id']}/proposals",
                {
                    "content": "Fictional draft version two. Review required.",
                    "base_revision_id": created["current_revision_id"],
                    "note": "Fictional confirmed revision for restart qualification.",
                },
            )["proposal"]
            committed = request(
                helper,
                "POST",
                first_base,
                f"/api/document-workspace/documents/{created['document_id']}/commit",
                {
                    "revision_id": proposal["revision_id"],
                    "confirmation_token": proposal["confirmation_token"],
                    "confirmed": True,
                },
            )["document"]
            before_state = safe_document_state(committed)
            audit_before = request(helper, "GET", first_base, "/api/document-workspace/audit/verify")
            first_bound = helper.verify_runtime_instance(first_base, process.qa_service_instance)
            first_network = first_monitor.stop()
            first_monitor = None
            terminate(process)
            process = None

            second_port = helper.free_port()
            second_base = f"http://127.0.0.1:{second_port}"
            process = helper.start_runtime(runtime, second_port, localappdata=localappdata)
            second_monitor = helper.RuntimeNetworkMonitor(process.pid)
            second_monitor.start()
            health_after = helper.wait_json(f"{second_base}/api/health", timeout_s=180)
            second_bound = helper.verify_runtime_instance(second_base, process.qa_service_instance)
            if not second_bound:
                raise RuntimeError("second_runtime_instance_mismatch")
            activated_after = request(helper, "POST", second_base, "/api/activate-corpus", {"case_root": str(case_root)})
            reopened = request(
                helper,
                "GET",
                second_base,
                f"/api/document-workspace/documents/{created['document_id']}",
            )["document"]
            audit_after = request(helper, "GET", second_base, "/api/document-workspace/audit/verify")
            listed = request(helper, "GET", second_base, "/api/document-workspace/documents")
            second_bound = helper.verify_runtime_instance(second_base, process.qa_service_instance)
            second_network = second_monitor.stop()
            second_monitor = None

            after_state = safe_document_state(reopened)
            checks = {
                "first_runtime_instance_bound": first_bound,
                "second_runtime_instance_bound": second_bound,
                "first_health": health_before.get("status") == "ok",
                "first_activation": activated_before.get("status") == "ok",
                "draft_created_review_required": before_state["review_required"],
                "revision_committed": before_state["current_revision_id"] != before_state["original_revision_id"],
                "original_preserved": before_state["original_preserved"],
                "audit_before_valid": audit_before.get("valid") is True,
                "second_health": health_after.get("status") == "ok",
                "second_activation": activated_after.get("status") == "ok",
                "same_document_reopened": after_state["document_id"] == before_state["document_id"],
                "same_revision_reopened": after_state["current_revision_id"] == before_state["current_revision_id"],
                "same_content_reopened": after_state["content_sha256"] == before_state["content_sha256"],
                "review_required_after_restart": after_state["review_required"],
                "audit_after_valid": audit_after.get("valid") is True,
                "document_list_contains_reopened": any(
                    str(row.get("document_id") or "") == before_state["document_id"]
                    for row in list(listed.get("documents") or [])
                    if isinstance(row, dict)
                ),
            }
            report["network_observations"] = {
                "first": first_network, "second": second_network,
                "limitation": "Best-effort TCP polling is not OS-level zero-network evidence; DNS, UDP, short-lived or inaccessible sockets are not excluded.",
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "document": before_state,
                "reopened_document": after_state,
                "audit_event_count_before": int(audit_before.get("event_count") or 0),
                "audit_event_count_after": int(audit_after.get("event_count") or 0),
                "network_samples": int(first_network.get("sample_count") or 0) + int(second_network.get("sample_count") or 0),
            }
            failed = sorted(name for name, passed in checks.items() if not passed)
            if first_network.get("external_connection_count") or second_network.get("external_connection_count"):
                failed.append("external_connection_observed")
            report["blockers"] = failed
            report["decision"] = "PASS" if not failed else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"durable_restart_exception:{type(exc).__name__}"]
        finally:
            if first_monitor is not None:
                first_monitor.stop()
            if second_monitor is not None:
                second_monitor.stop()
            if process is not None:
                terminate(process)
    report["request_events"] = helper.REQUEST_EVENTS
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "ga_today" / "evidence" / "08_v8_durable_restart_e2e.json",
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Evidence already exists; choose a fresh output path.")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    try:
        report = run(runtime=runtime, package=package)
    except ValueError as exc:
        print(f"Durable restart qualification blocked: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}, indent=2))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
