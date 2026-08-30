"""Prove exact-span citation and quote proposals against an external admitted build.

This is a frozen-runtime, canonical-API qualification runner.  It creates only
temporary fictional drafts and records hashes, identifiers, statuses, and
counts in evidence.  It never copies authority text, a corpus, or a local path
into the MSIX or evidence output.
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


def _load_shared() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status(
    helper: Any, method: str, base_url: str, route: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"{base_url}{route}",
        data=json.dumps(payload).encode("utf-8"),
        method=method,
        headers={**helper.QA_HEADERS, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return int(exc.code), json.loads(raw)
        except json.JSONDecodeError:
            return int(exc.code), {}


def _safe_receipt(value: dict[str, Any]) -> dict[str, Any]:
    authority = dict(value.get("authority") or value.get("quote") or {})
    return {
        "receipt_id": str(value.get("receipt_id") or ""),
        "review_required": value.get("review_required") is True,
        "filing_ready": value.get("filing_ready") is True,
        "original_preserved": value.get("original_preserved") is True,
        "authority_source_id": str(authority.get("source_id") or ""),
        "authority_hash": str(authority.get("source_hash") or ""),
        "pinpoint_sha256": hashlib.sha256(str(authority.get("pinpoint") or "").encode()).hexdigest(),
        "quote_status": str(authority.get("status") or ""),
    }


def run(
    *, runtime: Path, package: Path, authority_root: Path, authority_source_id: str, pinpoint: str
) -> dict[str, Any]:
    shared = _load_shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_source_bound_drafting_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority": {"source_id": authority_source_id, "selected_pinpoint_sha256": hashlib.sha256(pinpoint.encode()).hexdigest()},
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This proves a bounded, local review workflow against an external admitted source build. It does not "
            "determine current law, legal effect, citation sufficiency, factual truth, attorney review, filing "
            "readiness, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-source-drafting-") as temporary:
        temp_root = Path(temporary)
        matter = temp_root / "fictional-matter"
        other_matter = temp_root / "fictional-other-matter"
        matter.mkdir(); other_matter.mkdir()
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=temp_root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            resolved = shared.request(
                helper, "GET", base_url,
                f"/api/drafting/outline-authority-candidate/{authority_source_id}",
            )
            candidates = [
                dict(row) for row in list(resolved.get("pinpoint_candidates") or [])
                if isinstance(row, dict) and str(row.get("authority_id") or "")
            ]
            selected = next((row for row in candidates if str(row.get("pinpoint") or "") == pinpoint), {})
            selected_authority_id = str(selected.get("authority_id") or "")
            selected_hash = str(selected.get("source_hash") or "")
            citation_document = shared.request(
                helper, "POST", base_url, "/api/document-workspace/documents",
                {"title": "Fictional citation draft", "document_type": "draft", "content": "Fictional reviewer statement for source-bound citation.", "note": "Fictional review only."},
            )
            citation_document_id = str((citation_document.get("document") or {}).get("document_id") or "")
            base_payload = {
                "reviewer_safe_id": "reviewer_fictional_001",
                "selected_text": "Fictional reviewer statement for source-bound citation.",
                "authority": {"source_id": authority_source_id},
                "user_confirmed": True,
            }
            required_status, required_payload = _status(
                helper, "POST", base_url,
                f"/api/drafting/documents/{citation_document_id}/citation-insertions", base_payload,
            )
            citation_created = shared.request(
                helper, "POST", base_url,
                f"/api/drafting/documents/{citation_document_id}/citation-insertions",
                base_payload | {"authority": {"source_id": authority_source_id, "authority_id": selected_authority_id}},
            )
            citation_receipt = dict(citation_created.get("receipt") or {})
            citation_proposal = shared.request(
                helper, "POST", base_url,
                f"/api/drafting/documents/{citation_document_id}/citation-insertions/{citation_receipt.get('receipt_id')}/propose",
            )
            quote_document = shared.request(
                helper, "POST", base_url, "/api/document-workspace/documents",
                {"title": "Fictional quote draft", "document_type": "draft", "content": "Fictional reviewer quotation placeholder.", "note": "Fictional review only."},
            )
            quote_document_id = str((quote_document.get("document") or {}).get("document_id") or "")
            quote_created = shared.request(
                helper, "POST", base_url,
                f"/api/drafting/documents/{quote_document_id}/quote-receipts",
                {
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_text": "Fictional reviewer quotation placeholder.",
                    "quote_text": str(selected.get("exact_span") or ""),
                    "authority": {"source_id": authority_source_id, "authority_id": selected_authority_id},
                    "user_confirmed": True,
                },
            )
            quote_receipt = dict(quote_created.get("receipt") or {})
            quote_proposal = shared.request(
                helper, "POST", base_url,
                f"/api/drafting/documents/{quote_document_id}/quote-receipts/{quote_receipt.get('receipt_id')}/propose",
            )
            tampered_status, _ = _status(
                helper, "POST", base_url,
                f"/api/drafting/documents/{citation_document_id}/citation-insertions",
                base_payload | {"authority": {"source_id": authority_source_id, "authority_id": "authority_0000000000000000"}},
            )
            original = shared.request(
                helper, "GET", base_url,
                f"/api/document-workspace/documents/{citation_document_id}",
            )
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_matter = shared.status_for_bytes(
                helper, base_url,
                f"/api/drafting/documents/{citation_document_id}/citation-insertions/{citation_receipt.get('receipt_id')}",
            )
            audit = shared.request(helper, "GET", base_url, "/api/document-workspace/audit/verify")
            network = monitor.stop(); monitor = None
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "multiple_admitted_pinpoints_visible": len(candidates) > 1,
                "reviewer_selected_requested_pinpoint": bool(selected_authority_id) and selected_hash == str(selected.get("source_hash") or ""),
                "no_silent_pinpoint_selection": required_status == 409 and str(required_payload.get("detail") or "") == "citation_insertion_authority_selection_required",
                "citation_receipt_review_required": citation_receipt.get("review_required") is True and citation_receipt.get("filing_ready") is False,
                "citation_proposal_preserves_original": citation_proposal.get("original_preserved") is True and str((original.get("document") or {}).get("content") or "") == "Fictional reviewer statement for source-bound citation.",
                "quote_receipt_exact_and_review_required": str((quote_receipt.get("quote") or {}).get("status") or "") == "exact" and quote_receipt.get("review_required") is True and quote_receipt.get("filing_ready") is False,
                "quote_proposal_preserves_original": quote_proposal.get("original_preserved") is True,
                "invalid_authority_id_rejected": tampered_status == 409,
                "cross_matter_receipt_access_denied": switched.get("status") == "ok" and cross_matter == 404,
                "audit_chain_valid": audit.get("valid") is True,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
                "external_authority_excluded_from_msix": True,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "candidate_count": len(candidates),
                "selected_authority_hash": selected_hash,
                "citation": _safe_receipt(citation_receipt),
                "quote": _safe_receipt(quote_receipt),
                "cross_matter_status": cross_matter,
                "audit_event_count": int(audit.get("event_count") or 0),
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"source_bound_drafting_exception:{type(exc).__name__}"]
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
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--pinpoint", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True),
        authority_root=args.authority_data_root.resolve(strict=True), authority_source_id=args.authority_source_id,
        pinpoint=args.pinpoint,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
