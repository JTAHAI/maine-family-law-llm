"""Audit guided-form reachability and its current-form fail-closed boundary.

The runner uses a disposable fictional matter.  A fully passing result requires
at least one admitted form marked current/fresh/verified_current; otherwise it
records the safe blocked path rather than inventing a current form.
"""

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
CURRENT = {"current", "fresh", "verified_current"}


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


def run(*, runtime: Path, package: Path, authority_root: Path) -> dict[str, Any]:
    shared = _shared(); shared.validate_runtime_pair(runtime, package); helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_guided_forms_e2e_v1", "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True, "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime),
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This is a review-only working-copy form check. It does not complete an official form, determine freshness, create a filing-ready document, or establish Store or Enterprise readiness.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-guided-forms-") as temporary:
        root = Path(temporary); matter, other = root / "fictional-matter", root / "fictional-other-matter"
        matter.mkdir(); other.mkdir(); process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            catalog = shared.request(helper, "GET", base_url, "/api/forms?limit=100")
            forms = [dict(row) for row in list(catalog.get("forms") or []) if isinstance(row, dict) and row.get("form_id") and row.get("source_id")]
            current_forms = [row for row in forms if str(row.get("freshness_status") or "").casefold() in CURRENT]
            selected = (current_forms or forms or [{}])[0]
            form_id = str(selected.get("form_id") or "")
            source_id = str(selected.get("source_id") or "")
            source = shared.request(helper, "GET", base_url, f"/api/authority/sources/{source_id}") if source_id else {}
            document_response = shared.request(helper, "POST", base_url, "/api/document-workspace/documents", {
                "title": "Fictional guided-form working copy", "document_type": "draft",
                "content": "Fictional working-copy information only.", "note": "Fictional form review; do not file.",
            })
            document = dict(document_response.get("document") or {}); document_id = str(document.get("document_id") or "")
            created = shared.request(helper, "POST", base_url, "/api/forms/session", {
                "document_id": document_id, "proceeding_type": "family_matter", "selected_form_ids": [form_id] if form_id else [], "approved": True,
            })
            session_id = str(created.get("session_id") or "")
            patched = shared.request(helper, "PATCH", base_url, f"/api/forms/session/{session_id}", {
                "form_values": {}, "reviewer_notes": "Fictional local working-copy note.", "selected_form_ids": [form_id] if form_id else [], "approved": True,
            }) if session_id else {}
            validated = shared.request(helper, "POST", base_url, f"/api/forms/session/{session_id}/validate", {"confirmed": True}) if session_id else {}
            receipt = shared.request(helper, "GET", base_url, f"/api/forms/session/{session_id}/receipt") if session_id else {}
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, f"/api/forms/session/{session_id}") if session_id else 0
            network = monitor.stop(); monitor = None
            encrypted_paths = list(matter.rglob("sessions.json.enc")); ciphertext = encrypted_paths[0].read_bytes() if len(encrypted_paths) == 1 else b""
            selected_freshness = str(selected.get("freshness_status") or "unknown").casefold()
            created_blockers = {str(item) for item in list(created.get("blockers") or [])}
            safety_checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "form_catalog_loaded": catalog.get("status") in {"pass", "review_required"},
                "official_form_source_drilldown": bool(source_id) and source.get("status") == "pass",
                "guided_session_created_review_required": bool(session_id) and created.get("review_required") is True,
                "session_patch_preserves_non_filing_boundary": patched.get("review_required") is True and patched.get("filing_ready") is False,
                "form_validation_remains_non_filing": validated.get("review_required") is True and validated.get("filing_ready") is False,
                "unverified_form_fails_closed": (selected_freshness in CURRENT) or f"form_not_verified_current:{form_id}" in created_blockers,
                "guided_session_state_encrypted_at_rest": len(encrypted_paths) == 1 and b"Fictional local working-copy note" not in ciphertext,
                "cross_matter_session_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in safety_checks.items()}
            report["artifacts"] = {
                "form_catalog_count": len(forms), "verified_current_form_count": len(current_forms),
                "selected_form_id": form_id, "selected_form_source_id": source_id, "selected_form_freshness": selected_freshness,
                "session_id": session_id, "validation_status": str(validated.get("status") or ""), "receipt_status": str(receipt.get("status") or ""),
                "encrypted_session_state_sha256": hashlib.sha256(ciphertext).hexdigest(), "cross_matter_status": cross_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in safety_checks.items() if not passed)
            if not current_forms:
                report["blockers"].append("verified_current_authority_form_unavailable")
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"guided_forms_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_data_root.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
