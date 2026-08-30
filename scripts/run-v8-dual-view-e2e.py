"""Exercise a source-linked plain-language dual view through a frozen runtime."""

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


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_dual_view_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_source_id": authority_source_id,
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This is a review-required working-copy proof, not a certified translation, legal conclusion, or filing-ready document.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-dual-view-") as temporary:
        temp_root = Path(temporary); matter = temp_root / "fictional-matter"; other = temp_root / "fictional-other-matter"
        matter.mkdir(); other.mkdir(); process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=temp_root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            source = shared.request(helper, "GET", base_url, f"/api/authority/sources/{authority_source_id}")
            source_card = dict(source.get("source_card") or {})
            # The canonical source-detail response exposes the admitted digest as
            # ``source_card.source_hash``.  Do not rely on a UI-only alias: this
            # runner records the actual resolver-provided identity used by the
            # fictional working copy.
            source_hash = str(source_card.get("source_hash") or source_card.get("hash") or source.get("hash") or source.get("source_hash") or "")
            document = shared.request(helper, "POST", base_url, "/api/document-workspace/documents", {
                "title": "Fictional legal review draft", "document_type": "draft",
                "content": "Fictional legal-review working copy with an official source reference.",
                "note": "Fictional review only.",
                "source_refs": [{"source_id": authority_source_id, "hash": source_hash, "source_class": str(source.get("source_class") or "official_authority")}],
            })
            doc = dict(document.get("document") or {}); document_id = str(doc.get("document_id") or "")
            created = shared.request(helper, "POST", base_url, f"/api/drafting/documents/{document_id}/dual-views", {
                "view_id": "fictional_plain_view_001", "reviewer_safe_id": "reviewer_fictional_001",
                "plain_language_text": "Fictional plain-language working copy for reviewer discussion.", "user_confirmed": True,
            })
            view = dict(created.get("view") or {})
            loaded = shared.request(helper, "GET", base_url, f"/api/drafting/documents/{document_id}/dual-views/fictional_plain_view_001")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, f"/api/drafting/documents/{document_id}/dual-views/fictional_plain_view_001")
            network = monitor.stop(); monitor = None
            encrypted_paths = list(matter.rglob("views.json.enc")); ciphertext = encrypted_paths[0].read_text(encoding="utf-8") if len(encrypted_paths) == 1 else ""
            checks = {
                "runtime_health": health.get("status") == "ok", "fictional_matter_activated": activated.get("status") == "ok",
                "official_source_drilldown_available": bool(source_hash),
                "view_created_review_required": created.get("review_required") is True and created.get("filing_ready") is False,
                "view_is_revision_and_source_linked": str(view.get("revision_id") or "") == str(doc.get("current_revision_id") or "") and int(view.get("source_ref_count") or 0) == 1 and str((view.get("source_refs") or [{}])[0].get("source_id") or "") == authority_source_id,
                "view_load_reports_current_revision": bool((loaded.get("view") or {}).get("current_revision_match")),
                "cross_matter_view_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "view_state_encrypted_at_rest": len(encrypted_paths) == 1 and "Fictional plain-language" not in ciphertext,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {"document_id": document_id, "view_id": str(view.get("view_id") or ""), "source_hash": source_hash, "encrypted_view_state_sha256": hashlib.sha256(ciphertext.encode()).hexdigest(), "cross_matter_status": cross_status, "network_samples": int(network.get("sample_count") or 0)}
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed); report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"dual_view_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path); parser.add_argument("--authority-data-root", required=True, type=Path); parser.add_argument("--authority-source-id", required=True); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_data_root.resolve(strict=True), authority_source_id=args.authority_source_id)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]})); return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
