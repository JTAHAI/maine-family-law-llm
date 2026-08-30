"""Exercise a source-bound draft outline through an exact frozen MSIX runtime.

This runner uses only a disposable fictional matter.  It can use an explicitly
named, external official-authority root for the source lane, but never copies
that root into the package or reports source text or local paths in evidence.
It proves a bounded local workflow, not that an authority is current law or
that the resulting review outline is legal advice, a factual finding, or
filing-ready.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_HELPER_PATH = ROOT / "scripts" / "run-installed-offline-qualification.py"
HEX_64 = re.compile(r"[a-f0-9]{64}\Z")
EXTERNAL_AUTHORITY_PACKAGE_PREFIXES = (
    "official_authority_store/",
    "parsed_authority_store/",
    "embedding_store/",
    "eval_store/",
)


def load_helper() -> Any:
    specification = importlib.util.spec_from_file_location(
        "mfl_installed_offline_qualification", QUALIFICATION_HELPER_PATH
    )
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
    if not runtime.is_file() or not package.is_file():
        raise ValueError("runtime_or_package_missing")
    if runtime.resolve().parent.name != "runtime" or package.resolve().parent.name != "msix":
        raise ValueError("runtime_is_not_paired_with_supplied_msix")
    try:
        with zipfile.ZipFile(package) as archive:
            members = archive.namelist()
            forbidden = [
                member
                for member in members
                if any(member.casefold().startswith(prefix) for prefix in EXTERNAL_AUTHORITY_PACKAGE_PREFIXES)
            ]
            if forbidden:
                raise ValueError("package_contains_external_authority_data")
            candidates = [member for member in members if member.casefold() == "mainefamilylawllm.exe"]
            if len(candidates) != 1:
                raise ValueError("package_executable_unverifiable")
            packaged_hash = hashlib.sha256(archive.read(candidates[0])).hexdigest()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("package_executable_unverifiable") from exc
    if packaged_hash != sha256_file(runtime):
        raise ValueError("runtime_bytes_differ_from_supplied_msix")


def authority_provenance(authority_root: Path, source_id: str) -> dict[str, Any]:
    manifest = authority_root / "official_authority_store" / "source_manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("external_authority_manifest_missing")
    try:
        rows = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("external_authority_manifest_unreadable") from exc
    if not isinstance(rows, list):
        raise ValueError("external_authority_manifest_invalid")
    row = next((item for item in rows if isinstance(item, dict) and item.get("source_id") == source_id), None)
    if not isinstance(row, dict):
        raise ValueError("external_authority_source_missing")
    source_hash = str(row.get("hash") or "").casefold()
    if not HEX_64.fullmatch(source_hash):
        raise ValueError("external_authority_source_hash_invalid")
    if str(row.get("jurisdiction") or "").casefold() != "maine":
        raise ValueError("external_authority_jurisdiction_invalid")
    return {
        "source_id": source_id,
        "source_hash": source_hash,
        "source_class": str(row.get("source_class") or "unknown")[:80],
        "freshness_status": str(row.get("freshness_status") or "unknown")[:80],
        "retrieved_at": str(row.get("retrieved_at") or "")[:80],
        "manifest_sha256": sha256_file(manifest),
    }


def request(
    helper: Any,
    method: str,
    base_url: str,
    route: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return helper.request_json(method, f"{base_url}{route}", payload)


def status_for_bytes(helper: Any, base_url: str, route: str) -> int:
    call = urllib.request.Request(f"{base_url}{route}", headers=helper.QA_HEADERS)
    try:
        with urllib.request.urlopen(call, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001
        process.kill()
        process.wait(timeout=30)


def safe_outline_state(outline: dict[str, Any]) -> dict[str, Any]:
    evidence = list(outline.get("evidence") or [])
    authority = list(outline.get("authority") or [])
    return {
        "outline_id": str(outline.get("outline_id") or ""),
        "evidence_lane": str((evidence[0] if evidence else {}).get("lane") or ""),
        "authority_lane": str((authority[0] if authority else {}).get("lane") or ""),
        "evidence_source_hash": str((evidence[0] if evidence else {}).get("source_hash") or ""),
        "authority_source_hash": str((authority[0] if authority else {}).get("source_hash") or ""),
        "review_required": outline.get("review_required") is True,
        "filing_ready": outline.get("filing_ready") is True,
        "draft_prose_created": outline.get("draft_prose_created") is True,
    }


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    validate_runtime_pair(runtime, package)
    provenance = authority_provenance(authority_root, authority_source_id)
    helper = load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_structured_outline_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": sha256_file(package),
        "runtime_sha256": sha256_file(runtime),
        "authority_provenance": provenance,
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "Fictional local-workflow evidence only. The external authority root remains outside the MSIX and its "
            "stored freshness status is reported without asserting currency. The outline is review-required and "
            "does not establish legal authority, facts, legal advice, filing readiness, attorney review, Store "
            "qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-outline-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter-a"
        case_root.mkdir()
        alternate_root = temporary_root / "fictional-matter-b"
        alternate_root.mkdir()
        records = helper.build_case_fixture(case_root)
        docx_record = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        expected_record_hash = str(docx_record.get("source_hash") or "")
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(
                runtime,
                port,
                localappdata=temporary_root / "localappdata",
                authority_data_root=authority_root,
            )
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activation = request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            candidates = request(helper, "GET", base_url, "/api/drafting/outline-evidence-candidates")
            private_candidate = next(
                (row for row in list(candidates.get("candidates") or []) if row.get("record_id") == "REC-DOCX"),
                {},
            )
            authority_candidate_response = request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/outline-authority-candidate/{authority_source_id}",
            )
            authority_candidate = dict(authority_candidate_response.get("candidate") or {})
            created = request(
                helper,
                "POST",
                base_url,
                "/api/drafting/outlines",
                {
                    "outline_id": "outline_fictional_001",
                    "issue_id": "issue_fictional_001",
                    "issue_label": "Fictional source organization issue",
                    "purpose": "Organize fictional source references before prose.",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_evidence": [
                        {
                            "record_id": str(private_candidate.get("record_id") or ""),
                            "source_hash": str(private_candidate.get("source_hash") or ""),
                        }
                    ],
                    "selected_authority": [authority_candidate],
                    "user_confirmed": True,
                },
            )
            outline = dict(created.get("outline") or {})
            outline_id = str(outline.get("outline_id") or "")
            evidence_source = request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/outlines/{outline_id}/evidence/REC-DOCX/source",
            )
            authority_id = str((list(outline.get("authority") or [{}])[0]).get("authority_id") or "")
            authority_source = request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/outlines/{outline_id}/authority/{authority_id}/source",
            )
            source_token = str((evidence_source.get("source") or {}).get("source_token") or "")
            private_source_status = (
                status_for_bytes(helper, base_url, f"/api/records/open/{source_token}")
                if HEX_64.fullmatch(source_token)
                else 0
            )
            encrypted_outline = case_root / "19_DRAFTING" / "outline-workbench" / "outlines.json.enc"
            encrypted_at_rest = (
                encrypted_outline.is_file()
                and not encrypted_outline.is_symlink()
                and b"Fictional source organization issue" not in encrypted_outline.read_bytes()
            )
            alternate = request(
                helper,
                "POST",
                base_url,
                "/api/activate-corpus",
                {"case_root": str(alternate_root)},
            )
            cross_matter_status = status_for_bytes(
                helper, base_url, f"/api/drafting/outlines/{outline_id}"
            )
            network = monitor.stop()
            monitor = None
            state = safe_outline_state(outline)
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "authority_candidate_hash_matches_external_manifest": str(authority_candidate.get("source_hash") or "") == provenance["source_hash"],
                "private_record_hash_bound": str(private_candidate.get("source_hash") or "") == expected_record_hash,
                "separate_source_lanes": state.get("evidence_lane") == "private_matter_record" and state.get("authority_lane") == "official_authority",
                "review_required_not_filing_ready": state.get("review_required") is True and state.get("filing_ready") is False and state.get("draft_prose_created") is False,
                "private_source_drilldown": private_source_status == 200 and str((evidence_source.get("source") or {}).get("source_hash") or "") == expected_record_hash,
                "authority_source_drilldown": str((authority_source.get("source") or {}).get("source_hash") or "") == provenance["source_hash"],
                "encrypted_outline_at_rest": encrypted_at_rest,
                "cross_matter_access_denied": alternate.get("status") == "ok" and cross_matter_status == 404,
                "external_authority_excluded_from_msix": True,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "outline": state,
                "private_source_open_status": private_source_status,
                "cross_matter_outline_status": cross_matter_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"structured_outline_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable,
        package=args.package,
        authority_root=args.authority_data_root,
        authority_source_id=args.authority_source_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
