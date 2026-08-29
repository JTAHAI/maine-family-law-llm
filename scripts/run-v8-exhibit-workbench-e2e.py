"""Exercise frozen exhibit-review workflows with disposable fictional records.

This runner proves two deliberately narrow local workflows against the
executable paired with the supplied MSIX: an exhibit admission-preparation
checklist and a chain-of-custody receipt.  It emits identifiers, hashes,
statuses, and counts only—never record text, local paths, or review notes.
Neither workflow determines authenticity, foundation, admissibility, or any
other legal conclusion.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
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


def request(helper: Any, method: str, base_url: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.request_json(method, f"{base_url}{route}", payload)


def terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001
        process.kill()
        process.wait(timeout=30)


def safe_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    categories = checklist.get("categories") or {}
    unresolved = sum(
        1
        for rows in categories.values()
        if isinstance(rows, list)
        for row in rows
        if isinstance(row, dict) and row.get("state") == "unresolved"
    )
    return {
        "checklist_id": str(checklist.get("checklist_id") or ""),
        "exhibit_id": str(checklist.get("exhibit_id") or ""),
        "category_count": len(categories) if isinstance(categories, dict) else 0,
        "unresolved_prompt_count": unresolved,
        "review_required": checklist.get("review_required") is True,
        "admissibility": str(checklist.get("admissibility") or ""),
        "authenticity": str(checklist.get("authenticity") or ""),
        "foundation": str(checklist.get("foundation") or ""),
    }


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    validate_runtime_pair(runtime, package)
    helper = load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_exhibit_workbench_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "package_sha256": sha256_file(package),
        "runtime_sha256": sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "Fictional local-workflow evidence only. The workflow records review-required prompts and local integrity receipts; "
            "it does not establish authenticity, foundation, admissibility, legal authority, attorney review, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-exhibit-e2e-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        records = helper.build_case_fixture(case_root)
        record = next((row for row in records if str(row.get("evidence_id") or "") == "REC-OCR"), records[0])
        source_record_id = str(record["evidence_id"])
        source_hash = str(record["source_hash"])
        localappdata = temporary_root / "localappdata"
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=localappdata)
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activation = request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            candidates = request(
                helper,
                "POST",
                base_url,
                "/api/exhibits/candidates",
                {
                    "candidates": [
                        {
                            "exhibit_id": "fictional_exhibit_ocr",
                            "original_record_id": source_record_id,
                            "original_hash": source_hash,
                            "description": "Fictional scan selected for exhibit review.",
                            "page_count": 1,
                        }
                    ]
                },
            )
            checklist = request(
                helper,
                "POST",
                base_url,
                "/api/exhibits/admission-checklists",
                {
                    "checklist_id": "fictional_admission_001",
                    "exhibit_id": "fictional_exhibit_ocr",
                    "reviewer_safe_id": "fictional_reviewer_001",
                    "reviewer_note": "Fictional review context.",
                },
            )
            checklist_source = request(
                helper,
                "GET",
                base_url,
                "/api/exhibits/admission-checklists/fictional_admission_001/source",
            )
            collection = request(
                helper,
                "POST",
                base_url,
                "/api/exhibits/custody-events",
                {
                    "event_id": "fictional_custody_001",
                    "exhibit_id": "fictional_exhibit_ocr",
                    "event_type": "collection",
                    "actor_safe_id": "fictional_reviewer_001",
                    "occurred_at_claimed": "fictional claimed time",
                    "details": "Fictional user-confirmed collection observation.",
                    "user_confirmed": True,
                },
            )
            transfer = request(
                helper,
                "POST",
                base_url,
                "/api/exhibits/custody-events",
                {
                    "event_id": "fictional_custody_002",
                    "exhibit_id": "fictional_exhibit_ocr",
                    "event_type": "transfer",
                    "actor_safe_id": "fictional_reviewer_001",
                    "occurred_at_claimed": "fictional claimed time",
                    "details": "Fictional user-confirmed transfer observation.",
                    "user_confirmed": True,
                },
            )
            custody_source = request(
                helper,
                "GET",
                base_url,
                "/api/exhibits/custody-events/fictional_custody_002/source",
            )
            custody_verify = request(helper, "GET", base_url, "/api/exhibits/custody-events/verify")
            network = monitor.stop()
            monitor = None

            checklist_state = safe_checklist(checklist)
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "candidate_review_required": candidates.get("review_required") is True and candidates.get("local_only") is True,
                "checklist_review_required": checklist_state["review_required"],
                "checklist_has_four_unresolved_categories": checklist_state["category_count"] == 4 and checklist_state["unresolved_prompt_count"] == 4,
                "checklist_declines_legal_conclusion": (
                    checklist_state["admissibility"] == "not_determined"
                    and checklist_state["authenticity"] == "not_determined"
                    and checklist_state["foundation"] == "not_determined"
                ),
                "checklist_source_hash_bound": checklist_source.get("source_hash") == source_hash and checklist_source.get("review_required") is True,
                "custody_events_review_required": collection.get("review_required") is True and transfer.get("review_required") is True,
                "custody_source_hash_bound": custody_source.get("source_hash") == source_hash and custody_source.get("review_required") is True,
                "custody_chain_integrity_valid": custody_verify.get("integrity_valid") is True and int(custody_verify.get("event_count") or 0) == 2,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "candidate": {
                    "exhibit_id": "fictional_exhibit_ocr",
                    "source_record_id": source_record_id,
                    "source_hash": source_hash,
                },
                "admission_checklist": checklist_state,
                "custody": {
                    "event_ids": [str(collection.get("event_id") or ""), str(transfer.get("event_id") or "")],
                    "event_count": int(custody_verify.get("event_count") or 0),
                    "integrity_valid": custody_verify.get("integrity_valid") is True,
                    "source_hash": str(custody_source.get("source_hash") or ""),
                },
                "network_samples": int(network.get("sample_count") or 0),
            }
            failed = sorted(name for name, passed in checks.items() if not passed)
            report["blockers"] = failed
            report["decision"] = "PASS" if not failed else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"exhibit_workbench_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "ga_today" / "evidence" / "08_v8_exhibit_workbench_e2e.json",
    )
    args = parser.parse_args(argv)
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    try:
        report = run(runtime=runtime, package=package)
    except ValueError as exc:
        print(f"Exhibit-workbench qualification blocked: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}, indent=2))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
