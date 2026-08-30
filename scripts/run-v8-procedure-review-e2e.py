"""Exercise the review-only procedure workspaces through a frozen runtime.

The harness uses one disposable fictional matter plus an explicitly named,
external authority root.  It proves bounded local software behavior only: it
does not calculate an actual deadline, establish service, venue, eligibility,
court acceptance, current law, filing readiness, or a legal conclusion.
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


def _shared() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _source_status(helper: Any, base_url: str, token: str) -> int:
    if len(token) != 64:
        return 0
    request = urllib.request.Request(
        f"{base_url}/api/records/open/{token}", headers={**helper.QA_HEADERS, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def _status(helper: Any, base_url: str, route: str) -> int:
    request = urllib.request.Request(
        f"{base_url}{route}", headers={**helper.QA_HEADERS, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def _text(base_url: str, route: str) -> tuple[int, str]:
    request = urllib.request.Request(
        f"{base_url}{route}", headers={"Accept": "application/javascript,text/plain"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _ciphertext_check(case_root: Path, relative_path: str, forbidden: str) -> bool:
    path = case_root / relative_path
    return path.is_file() and forbidden.encode("utf-8") not in path.read_bytes()


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    authority = shared.authority_provenance(authority_root, authority_source_id)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_procedure_review_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_provenance": authority,
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "The external authority root remains outside the MSIX. This proves only fictional, review-required "
            "local workflow behavior; it does not establish court procedure, a deadline, effective service, venue, "
            "fee-waiver eligibility, a court filing, court acceptance, current law, attorney review, Store "
            "qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-procedure-review-") as temporary:
        root = Path(temporary)
        matter, other_matter = root / "fictional-matter", root / "other-fictional-matter"
        matter.mkdir()
        other_matter.mkdir()
        records = helper.build_case_fixture(matter)
        record = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        record_hash = str(record.get("source_hash") or "")
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(
                runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root
            )
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            ui_status, workbench_js = _text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            matrix_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/service-method-matrices",
                {
                    "matrix_id": "fictional_service_matrix_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_method": "mail_service",
                    "proof": {"record_id": "REC-DOCX", "source_hash": record_hash, "page_number": 1},
                    "authority_source_id": authority_source_id,
                    "exceptions": ["Fictional recipient identity needs review."],
                    "unresolved_facts": ["Fictional mailing date has not been confirmed."],
                    "user_confirmed": True,
                },
            )
            matrix = dict(matrix_response.get("matrix") or {})
            matrix_private = shared.request(
                helper, "GET", base_url, "/api/service-method-matrices/fictional_service_matrix_001/private_matter_record/source"
            )
            matrix_authority = shared.request(
                helper, "GET", base_url, "/api/service-method-matrices/fictional_service_matrix_001/official_authority/source"
            )

            calendar_input_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/business-day-calendar-inputs",
                {
                    "input_id": "fictional_calendar_2026",
                    "calendar_key": "fictional_maine_review",
                    "version_label": "Fictional reviewer-entered 2026 calendar",
                    "jurisdiction_label": "Fictional Maine review context",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "valid_from": "2026-01-01",
                    "valid_through": "2026-12-31",
                    "holidays": ["2026-01-05"],
                    "authority_source_id": authority_source_id,
                    "user_confirmed": True,
                },
            )
            calendar_input = dict(calendar_input_response.get("input") or {})
            calculation_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/business-day-calculations",
                {
                    "calculation_id": "fictional_business_calc_001",
                    "input_id": "fictional_calendar_2026",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "start_date": "2026-01-02",
                    "business_days": 3,
                    "user_confirmed": True,
                },
            )
            calculation = dict(calculation_response.get("calculation") or {})
            calendar_authority = shared.request(
                helper, "GET", base_url, "/api/business-day-calendar-inputs/fictional_calendar_2026/authority/source"
            )

            countdown_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/hearing-countdowns",
                {
                    "countdown_id": "fictional_hearing_countdown_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "hearing_label": "Fictional review hearing",
                    "confirmed_date": "2026-02-20",
                    "notice_source": {"record_id": "REC-DOCX", "source_hash": record_hash, "page_number": 1},
                    "milestone_offsets": [14, 7, 1, 0],
                    "missing_proof_prompts": ["Confirm fictional exhibit source."],
                    "user_confirmed": True,
                },
            )
            countdown = dict(countdown_response.get("countdown") or {})
            countdown_source = shared.request(
                helper, "GET", base_url, "/api/hearing-countdowns/fictional_hearing_countdown_001/notice-source"
            )

            preflight_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/filing-preflights",
                {
                    "preflight_id": "fictional_preflight_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "caption_label": "Fictional caption review",
                    "attachments": [{"record_id": "REC-DOCX", "source_hash": record_hash, "page_number": 1, "declared_format": "docx"}],
                    "form_source_ids": [authority_source_id],
                    "checks": {
                        "caption_confirmed": True,
                        "names_confirmed": True,
                        "signatures_confirmed": True,
                        "format_confirmed": True,
                        "redactions_confirmed": True,
                        "privacy_review_complete": True,
                        "human_review_complete": True,
                    },
                    "document_id": "",
                    "user_confirmed": True,
                },
            )
            preflight = dict(preflight_response.get("preflight") or {})
            preflight_attachment = shared.request(
                helper,
                "GET",
                base_url,
                "/api/filing-preflights/fictional_preflight_001/private_matter_record/REC-DOCX/source",
            )

            fee_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/fee-waiver-workspaces",
                {
                    "workspace_id": "fictional_fee_workspace_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "purpose_label": "Fictional fee information question",
                    "authority_source_id": authority_source_id,
                    "facts": [{"fact_id": "fact_001", "label": "Household size", "user_entered_value": "Fictional value"}],
                    "user_confirmed": True,
                },
            )
            fee = dict(fee_response.get("workspace") or {})
            fee_authority = shared.request(
                helper, "GET", base_url, "/api/fee-waiver-workspaces/fictional_fee_workspace_001/authority/source"
            )

            venue_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/venue-location-workspaces",
                {
                    "workspace_id": "fictional_venue_workspace_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "location_label": "Fictional public court location",
                    "contact_label": "Fictional public contact",
                    "unresolved_facts": ["Residency fact requires review."],
                    "authority_source_id": authority_source_id,
                    "user_confirmed": True,
                },
            )
            venue = dict(venue_response.get("workspace") or {})
            venue_authority = shared.request(
                helper, "GET", base_url, "/api/venue-location-workspaces/fictional_venue_workspace_001/authority/source"
            )

            reconciliation_response = shared.request(
                helper,
                "POST",
                base_url,
                "/api/post-filing-reconciliations",
                {
                    "reconciliation_id": "fictional_post_filing_001",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "receipt_source": {"record_id": "REC-DOCX", "source_hash": record_hash},
                    "submitted_items": [{"record_id": "REC-DOCX", "source_hash": record_hash, "submitted_filename": "fictional-document.docx"}],
                    "docket_expectations": [{"expectation_id": "expectation_001", "expected_filename": "fictional-document.docx", "expected_hash": record_hash}],
                    "user_confirmed": True,
                },
            )
            reconciliation = dict(reconciliation_response.get("reconciliation") or {})
            reconciliation_source = shared.request(
                helper, "GET", base_url, "/api/post-filing-reconciliations/fictional_post_filing_001/sources/REC-DOCX"
            )

            source_statuses = {
                "service_proof": _source_status(helper, base_url, str((matrix_private.get("source") or {}).get("source_token") or "")),
                "hearing_notice": _source_status(helper, base_url, str((countdown_source.get("source") or {}).get("source_token") or "")),
                "preflight_attachment": _source_status(helper, base_url, str((preflight_attachment.get("source") or {}).get("source_token") or "")),
                "post_filing_record": _source_status(helper, base_url, str((reconciliation_source.get("source") or {}).get("source_token") or "")),
            }
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_statuses = {
                "service_matrix": _status(helper, base_url, "/api/service-method-matrices/fictional_service_matrix_001"),
                "business_input": _status(helper, base_url, "/api/business-day-calendar-inputs/fictional_calendar_2026"),
                "hearing_countdown": _status(helper, base_url, "/api/hearing-countdowns/fictional_hearing_countdown_001"),
                "preflight": _status(helper, base_url, "/api/filing-preflights/fictional_preflight_001"),
                "fee_workspace": _status(helper, base_url, "/api/fee-waiver-workspaces/fictional_fee_workspace_001"),
                "venue_workspace": _status(helper, base_url, "/api/venue-location-workspaces/fictional_venue_workspace_001"),
                "reconciliation": _status(helper, base_url, "/api/post-filing-reconciliations/fictional_post_filing_001"),
            }
            network = monitor.stop()
            monitor = None
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "shipped_production_ui_entries_present": ui_status == 200 and all(
                    value in workbench_js for value in (
                        "Service-method rules matrix", "/api/service-method-matrices",
                        "Business-day review", "/api/business-day-calendar-inputs",
                        "Hearing preparation countdown", "/api/hearing-countdowns",
                        "Filing package preflight", "/api/filing-preflights",
                        "Fee and waiver information", "/api/fee-waiver-workspaces",
                        "Venue and court-location navigator", "/api/venue-location-workspaces",
                        "Post-filing receipt reconciliation", "/api/post-filing-reconciliations",
                    )
                ),
                "service_matrix_review_only_with_private_and_authority_lanes": matrix.get("review_required") is True and matrix.get("filing_ready") is False and matrix.get("service_effectiveness") == "not_determined" and (matrix_private.get("source") or {}).get("source_hash") == record_hash and bool((matrix_authority.get("source") or {}).get("source_hash")),
                "business_day_input_and_candidate_review_only": bool(calendar_input.get("input_hash")) and calculation.get("candidate_date") == "2026-01-08" and calculation.get("review_required") is True and calculation.get("deadline_determined") is False and bool((calendar_authority.get("source") or {}).get("source_hash")),
                "hearing_countdown_review_only": countdown.get("review_required") is True and countdown.get("court_calendar_write") is False and (countdown_source.get("source") or {}).get("source_hash") == record_hash,
                "filing_preflight_remains_blocked": preflight.get("review_required") is True and preflight.get("filing_ready") is False and "canonical_reviewed_filing_packet_not_seen" in list(preflight.get("blockers") or []),
                "fee_workspace_keeps_facts_unverified": fee.get("review_required") is True and fee.get("filing_ready") is False and fee.get("eligibility") == "not_determined" and bool((fee_authority.get("source") or {}).get("source_hash")),
                "venue_workspace_is_non_determinative": venue.get("review_required") is True and venue.get("filing_ready") is False and venue.get("venue_determined") is False and bool((venue_authority.get("source") or {}).get("source_hash")),
                "post_filing_reconciliation_is_non_confirmatory": reconciliation.get("review_required") is True and reconciliation.get("filing_ready") is False and reconciliation.get("court_receipt_confirmed") is False and str((list(reconciliation.get("decisions") or [{}])[0]).get("status") or "") == "exact_match",
                "private_source_drill_downs_reopen": all(status == 200 for status in source_statuses.values()),
                "encrypted_review_sidecars": all((
                    _ciphertext_check(matter, "18_PROCEDURE/service-method-matrices/matrices.json.enc", "Fictional mailing date"),
                    _ciphertext_check(matter, "22_CALENDAR_REVIEW/business-days/business-days.json.enc", "Fictional reviewer-entered"),
                    _ciphertext_check(matter, "27_HEARING_PREPARATION/countdowns/countdowns.json.enc", "Fictional review hearing"),
                    _ciphertext_check(matter, "38_FILING_READINESS/preflight-v2/preflights.json.enc", "Fictional caption review"),
                    _ciphertext_check(matter, "38_FILING_READINESS/fee-waiver/workspaces.json.enc", "Fictional fee information"),
                    _ciphertext_check(matter, "18_PROCEDURE/venue-locations/workspaces.json.enc", "Fictional public court"),
                    _ciphertext_check(matter, "23_DOCKET_RECONCILIATION/post-filing/reconciliations.json.enc", "fictional-document.docx"),
                )),
                "cross_matter_access_denied": switched.get("status") == "ok" and all(status == 404 for status in cross_statuses.values()),
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "source_hash": record_hash,
                "authority_source_id": authority_source_id,
                "source_drill_down_statuses": source_statuses,
                "cross_matter_statuses": cross_statuses,
                "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
                "review_sidecar_hashes": {
                    path.relative_to(matter).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(matter.rglob("*.enc"))
                    if path.relative_to(matter).as_posix() in {
                        "18_PROCEDURE/service-method-matrices/matrices.json.enc",
                        "22_CALENDAR_REVIEW/business-days/business-days.json.enc",
                        "27_HEARING_PREPARATION/countdowns/countdowns.json.enc",
                        "38_FILING_READINESS/preflight-v2/preflights.json.enc",
                        "38_FILING_READINESS/fee-waiver/workspaces.json.enc",
                        "18_PROCEDURE/venue-locations/workspaces.json.enc",
                        "23_DOCKET_RECONCILIATION/post-filing/reconciliations.json.enc",
                    }
                },
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"procedure_review_exception:{type(exc).__name__}"]
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
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable.resolve(strict=True),
        package=args.package.resolve(strict=True),
        authority_root=args.authority_root.resolve(strict=True),
        authority_source_id=str(args.authority_source_id),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
