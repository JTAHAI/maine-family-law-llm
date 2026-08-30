"""Exercise a review-only, source-snapshot export through the frozen runtime."""

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
    if spec is None or spec.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status(helper: Any, method: str, base_url: str, route: str) -> int:
    request = urllib.request.Request(f"{base_url}{route}", method=method, headers={**helper.QA_HEADERS, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def _download(helper: Any, base_url: str, route: str) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(f"{base_url}{route}", headers={**helper.QA_HEADERS, "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(response.status), response.read(), {key.casefold(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return int(exc.code), body, {key.casefold(): value for key, value in exc.headers.items()}


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = _shared(); shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_export_provenance_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime),
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This proves a local review-only export and provenance receipt. It does not certify a filing, source authenticity, legal sufficiency, court acceptance, Store qualification, or Enterprise GA.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-export-provenance-") as temporary:
        root = Path(temporary); matter, other = root / "fictional-matter", root / "fictional-other-matter"
        matter.mkdir(); other.mkdir(); process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            source = shared.request(helper, "GET", base_url, f"/api/authority/sources/{authority_source_id}")
            card = dict(source.get("source_card") or {})
            source_hash = str(card.get("source_hash") or "")
            document_response = shared.request(helper, "POST", base_url, "/api/document-workspace/documents", {
                "title": "Fictional review-only export", "document_type": "draft",
                "content": "Fictional review-only draft body.", "note": "Fictional matter; do not file.",
                "source_refs": [{"source_id": authority_source_id, "hash": source_hash, "source_class": str(card.get("source_class") or "official_authority")}],
            })
            document = dict(document_response.get("document") or {}); document_id = str(document.get("document_id") or "")
            session = shared.request(helper, "POST", base_url, f"/api/document-workspace/documents/{document_id}/export-sessions?format=txt")
            download_route = str(session.get("download_url") or "")
            download_status, body, headers = _download(helper, base_url, download_route)
            receipt_id = str(headers.get("x-mfll-export-provenance-receipt") or "")
            receipts = shared.request(helper, "GET", base_url, f"/api/document-workspace/documents/{document_id}/export-provenance")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, f"/api/document-workspace/documents/{document_id}/export-provenance")
            network = monitor.stop(); monitor = None
            encrypted_paths = list(matter.rglob("receipts.json.enc"))
            ciphertext = encrypted_paths[0].read_bytes() if len(encrypted_paths) == 1 else b""
            completed = dict((list(receipts.get("receipts") or [{}])[-1]))
            footer_present = b"LOCAL EXPORT PROVENANCE" in body and b"review-required" in body.lower()
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "canonical_source_detail_available": source.get("status") == "pass" and bool(source_hash),
                "export_session_review_required_non_filing": session.get("review_required") is True and session.get("filing_ready") is False,
                "export_download_has_server_generated_review_footer": download_status == 200 and footer_present and receipt_id.startswith("export_"),
                "receipt_completed_and_bound_to_revision": completed.get("status") == "completed" and str(completed.get("document_id") or "") == document_id and str(completed.get("revision_id") or "") == str(document.get("current_revision_id") or "") and str(completed.get("source_snapshot_sha256") or ""),
                "footer_and_receipt_do_not_expose_raw_matter_path": str(matter).encode() not in body and str(matter) not in json.dumps(completed),
                "receipt_state_encrypted_at_rest": len(encrypted_paths) == 1 and b"Fictional review-only draft body" not in ciphertext,
                "cross_matter_receipt_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "document_id": document_id, "export_receipt_id": receipt_id,
                "artifact_sha256": hashlib.sha256(body).hexdigest(), "artifact_size_bytes": len(body),
                "source_snapshot_sha256": str(completed.get("source_snapshot_sha256") or ""),
                "encrypted_receipt_state_sha256": hashlib.sha256(ciphertext).hexdigest(),
                "cross_matter_status": cross_status, "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"export_provenance_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path); parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--output", required=True, type=Path); args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_data_root.resolve(strict=True), authority_source_id=args.authority_source_id)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
