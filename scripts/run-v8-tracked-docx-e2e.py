"""Exercise the frozen tracked-DOCX workflow with disposable fictional data.

The runner talks only to the canonical local API exposed by the frozen
executable paired with the supplied MSIX.  It reports hashes, identifiers and
workflow states; it deliberately never writes DOCX text, local paths, or
reviewer comments into its evidence output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_HELPER_PATH = ROOT / "scripts" / "run-installed-offline-qualification.py"
REQUIRED_DOCX_EDITOR_ASSETS = frozenset(
    {
        "_internal/docx_editor/ooxml/templates/comments.xml",
        "_internal/docx_editor/ooxml/templates/commentsExtended.xml",
        "_internal/docx_editor/ooxml/templates/commentsExtensible.xml",
        "_internal/docx_editor/ooxml/templates/commentsIds.xml",
        "_internal/docx_editor/ooxml/templates/people.xml",
    }
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
    expected_runtime = package.parent.parent / "runtime" / "MaineFamilyLawLLM.exe"
    if runtime.resolve() != expected_runtime.resolve():
        raise ValueError("runtime_is_not_paired_with_supplied_msix")
    try:
        with zipfile.ZipFile(package) as archive:
            members = archive.namelist()
            if members.count("MaineFamilyLawLLM.exe") != 1:
                raise ValueError("package_executable_missing_or_ambiguous")
            if not REQUIRED_DOCX_EDITOR_ASSETS.issubset(set(members)):
                raise ValueError("package_tracked_docx_assets_missing")
            with archive.open("MaineFamilyLawLLM.exe") as stream:
                packaged_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("package_executable_unverifiable") from exc
    if packaged_hash != sha256_file(runtime):
        raise ValueError("runtime_bytes_differ_from_supplied_msix")


def request(helper: Any, method: str, base_url: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.request_json(method, f"{base_url}{route}", payload)


def download_status(
    helper: Any,
    base_url: str,
    route: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    call = urllib.request.Request(f"{base_url}{route}", headers=headers or helper.QA_HEADERS)
    try:
        with urllib.request.urlopen(call, timeout=120) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001
        process.kill()
        process.wait(timeout=30)


def _document_text_contains(document_xml: bytes, expected: str) -> bool:
    """Check DOCX text semantically without retaining it in evidence.

    Word commonly splits a phrase across multiple ``w:t`` elements when it is
    wrapped in a tracked insertion.  Searching the raw XML therefore produces
    a false failure for an otherwise valid tracked edit.  We read the XML only
    in memory, concatenate text nodes, and return a boolean.
    """

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return False
    text = "".join(element.text or "" for element in root.iter() if element.tag.endswith("}t"))
    return expected.casefold() in text.casefold()


def safe_artifact_state(payload: dict[str, Any], artifact: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
        names = set(archive.namelist())
        document_xml = archive.read("word/document.xml")
    return {
        "artifact_id": str(payload.get("artifact_id") or ""),
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "declared_sha256": str(payload.get("sha256") or ""),
        "source_sha256": str(payload.get("source_sha256") or ""),
        "edit_count": int(payload.get("edit_count") or 0),
        "comments_part_present": "word/comments.xml" in names,
        "replacement_present": _document_text_contains(document_xml, "transferred schools"),
        "tracked_changes": payload.get("tracked_changes") is True,
        "original_preserved": payload.get("original_preserved") is True,
        "review_required": payload.get("review_required") is True,
        "filing_ready": payload.get("filing_ready") is True,
    }


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    validate_runtime_pair(runtime, package)
    helper = load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_tracked_docx_e2e_v2",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "package_sha256": sha256_file(package),
        "runtime_sha256": sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "execution_level": "frozen_runtime_canonical_api",
        "notice": (
            "Fictional local-workflow evidence only. The path creates a review-required tracked copy and proves an "
            "original-preservation boundary; it does not establish legal authority, authenticity, filing readiness, "
            "attorney review, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-tracked-docx-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        records = helper.build_case_fixture(case_root)
        docx_record = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        source_hash = str(docx_record["source_hash"])
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=temporary_root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activation = request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            integrity = request(helper, "GET", base_url, "/api/records/REC-DOCX/integrity")
            token = str((integrity.get("preview") or {}).get("token") or "")
            imported = request(
                helper,
                "POST",
                base_url,
                "/api/document-workspace/import-record",
                {
                    "source_token": token,
                    "title": "Fictional imported tracked-DOCX review",
                    "document_type": "draft",
                },
            )
            document = dict(imported.get("document") or {})
            document_id = str(document.get("document_id") or "")
            paragraphs = request(
                helper,
                "GET",
                base_url,
                f"/api/document-workspace/documents/{document_id}/docx/paragraphs?start=1&limit=20",
            )
            rows = list(paragraphs.get("paragraphs") or [])
            target = next(
                (
                    row
                    for row in rows
                    if "changed schools" in str(row.get("text") or "").lower()
                ),
                {},
            )
            tracked = request(
                helper,
                "POST",
                base_url,
                f"/api/document-workspace/documents/{document_id}/docx/tracked-edit",
                {
                    "confirmed": True,
                    "author": "fictional_reviewer_001",
                    "operations": [
                        {
                            "action": "replace",
                            "paragraph": str(target.get("ref") or ""),
                            "find": "changed schools",
                            "replace_with": "transferred schools",
                            "occurrence": 0,
                        },
                        {
                            "action": "add_comment",
                            "find": "Parent Jane Example",
                            "comment": "Fictional review comment.",
                            "occurrence": 0,
                        },
                    ],
                },
            )
            download_route = str(tracked.get("download_url") or "")
            first_status, artifact = download_status(helper, base_url, download_route)
            # A document artifact capability is bound to the browser session
            # that created it.  Use a different, well-formed session ID to
            # prove that a replay from another local session fails closed; do
            # not impose an unimplemented one-time-download rule that would
            # prevent a user retrying an interrupted private-file download.
            replay_headers = {
                **dict(helper.QA_HEADERS),
                "X-MFLL-Client-Session": "f" * 64,
            }
            second_status, _ = download_status(
                helper, base_url, download_route, headers=replay_headers
            )
            audit = request(helper, "GET", base_url, "/api/document-workspace/audit/verify")
            network = monitor.stop()
            monitor = None
            artifact_state = safe_artifact_state(tracked, artifact) if first_status == 200 else {}
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "docx_source_hash_bound": str((integrity.get("preview") or {}).get("source_hash") or "") == source_hash,
                "record_import_review_required": imported.get("review_required") is True and imported.get("original_preserved") is True,
                "hash_anchored_paragraphs_available": bool(rows) and bool(target.get("ref")) and paragraphs.get("source_sha256") == source_hash,
                "tracked_copy_review_required": artifact_state.get("review_required") is True and artifact_state.get("tracked_changes") is True,
                "original_preserved": artifact_state.get("original_preserved") is True,
                "tracked_copy_not_filing_ready": artifact_state.get("filing_ready") is False,
                "tracked_copy_hash_matches_receipt": artifact_state.get("artifact_sha256") == artifact_state.get("declared_sha256"),
                "tracked_replacement_and_comment_present": artifact_state.get("replacement_present") is True and artifact_state.get("comments_part_present") is True,
                "artifact_capability_session_bound": first_status == 200 and second_status == 404,
                "audit_chain_valid": audit.get("valid") is True,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "document_id": document_id,
                "source_hash": source_hash,
                "paragraph_count": len(rows),
                "tracked_copy": artifact_state,
                "audit_event_count": int(audit.get("event_count") or 0),
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"tracked_docx_exception:{type(exc).__name__}"]
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
        default=ROOT / "dist" / "ga_today" / "evidence" / "12_v8_tracked_docx_e2e.json",
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Evidence already exists; choose a fresh output path.")
    try:
        report = run(
            runtime=args.runtime_executable.resolve(strict=True),
            package=args.package.resolve(strict=True),
        )
    except ValueError as exc:
        print(f"Tracked-DOCX qualification blocked: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}, indent=2))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
