"""Exercise parenting, financial, and resolution review workspaces in frozen v8.

All inputs are disposable fictional data.  The runner verifies local software
boundaries and explicitly preserves the child-support current-authority block;
it does not determine a parenting plan, support, income, property, debt,
settlement, compliance, legal effect, or filing result.
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
PROCEDURE_RUNNER = ROOT / "scripts" / "run-v8-procedure-review-e2e.py"


def _procedure() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_v8_procedure_e2e", PROCEDURE_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("procedure_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _post_status(helper: Any, base_url: str, route: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{route}", data=body, method="POST",
        headers={**helper.QA_HEADERS, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return int(exc.code), {}


def _ciphertext(case_root: Path, relative: str, forbidden: str) -> bool:
    path = case_root / relative
    return path.is_file() and forbidden.encode("utf-8") not in path.read_bytes()


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    procedure = _procedure()
    shared = procedure._shared()
    shared.validate_runtime_pair(runtime, package)
    authority = shared.authority_provenance(authority_root, authority_source_id)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_family_finance_e2e_v1",
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
            "This is fictional, review-only, local software evidence. It does not determine parenting, custody, "
            "support, income, assets, debts, an agreement, compliance, current law, legal advice, filing readiness, "
            "attorney review, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-family-finance-") as temporary:
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
            ui_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            schedule = shared.request(helper, "POST", base_url, "/api/parenting-schedule/simulations-v2", {
                "simulation_id": "fictional_schedule_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "scenarios": [
                    {"scenario_id": "scenario_a", "label": "Fictional calendar A", "events": [
                        {"date_candidate": "2026-07-04", "label": "Holiday", "category": "holiday", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                        {"date_candidate": "2026-07-05", "label": "Travel", "category": "travel", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    ]},
                    {"scenario_id": "scenario_b", "label": "Fictional calendar B", "events": [
                        {"date_candidate": "2026-07-04", "label": "School", "category": "school", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                        {"date_candidate": "2026-07-07", "label": "Exchange", "category": "exchange", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    ]},
                ],
            })
            schedule_source = shared.request(helper, "GET", base_url, "/api/parenting-schedule/simulations-v2/fictional_schedule_001/sources/REC-DOCX")

            shared.request(helper, "POST", base_url, "/api/orders", {
                "orders": [{
                    "order_id": "fictional_order_001", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash, "page": 1},
                    "caption": "Fictional review order", "docket_safe_id": "fictional_docket_001", "court": "Fictional court",
                    "order_type": "order", "signed_date": "2026-06-01", "entered_date": "2026-06-01", "effective_date": "2026-06-01",
                    "signature_status": "review_required", "status_candidate": "unknown", "freshness_status": "unknown",
                    "terms": [{"term_id": "fictional_term_001", "subject": "holidays", "exact_language": "Fictional exact order term.", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash, "page": 1}, "dates": [], "party_safe_labels": [], "conditions": "", "exceptions": "", "parser_warnings": []}],
                }]
            })
            shared.request(helper, "POST", base_url, "/api/orders/operative-candidate-review", {
                "term_id": "fictional_term_001", "reviewer_safe_id": "reviewer_fictional_001", "confirmed": True, "note": "Fictional reviewer confirmation."
            })
            order_candidate = shared.request(helper, "POST", base_url, "/api/calendar/order-term-extractions", {
                "extraction_id": "fictional_order_calendar_001", "reviewer_safe_id": "reviewer_fictional_001", "term_id": "fictional_term_001", "date_candidate": "2026-07-04", "label": "Fictional calendar candidate", "user_confirmed": True,
            })
            order_source = shared.request(helper, "GET", base_url, "/api/calendar/order-term-extractions/fictional_order_calendar_001/source")

            child_support_status, child_support_error = _post_status(helper, base_url, "/api/child-support-worksheets", {
                "workspace_id": "fictional_support_001", "reviewer_safe_id": "reviewer_fictional_001", "authority_source_id": authority_source_id,
                "inputs": [{"input_id": "input_001", "field_id": "gross_income", "label": "Gross income", "value": "Fictional input", "state": "user_entered_unverified"}, {"input_id": "input_002", "field_id": "children", "label": "Children", "value": "", "state": "unknown"}],
                "missing_facts": ["Fictional missing fact"], "user_confirmed": True,
            })

            financial_response = shared.request(helper, "POST", base_url, "/api/financial-affidavit-workspaces", {
                "workspace_id": "fictional_financial_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "entries": [
                    {"entry_id": "entry_001", "category": "income", "label": "Fictional income A", "reported_value": "fictional amount A", "reconciliation_key": "income_001", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    {"entry_id": "entry_002", "category": "income", "label": "Fictional income B", "reported_value": "fictional amount B", "reconciliation_key": "income_001", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                ], "unknowns": ["Fictional unknown period"],
            })
            financial = dict(financial_response.get("workspace") or {})
            financial_source = shared.request(helper, "GET", base_url, "/api/financial-affidavit-workspaces/fictional_financial_001/entries/entry_001/source")

            assets_response = shared.request(helper, "POST", base_url, "/api/asset-tracing-ledgers", {
                "ledger_id": "fictional_asset_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "assets": [{"asset_id": "asset_001", "label": "Fictional asset", "claimed_source": "Reviewer-entered claimed source", "valuation_date": "2026-01-01", "transfers": [{"transfer_id": "transfer_001", "date_candidate": "2026-02-01", "description": "Reviewer-entered transfer note"}], "characterization_assertion": "Reviewer-entered characterization", "characterization_disputed": True, "supporting_records": [{"record_id": "REC-DOCX", "source_hash": record_hash}]}],
            })
            assets = dict(assets_response.get("ledger") or {})
            asset_source = shared.request(helper, "GET", base_url, "/api/asset-tracing-ledgers/fictional_asset_001/assets/asset_001/sources/REC-DOCX")

            debt_response = shared.request(helper, "POST", base_url, "/api/debt-reconciliation-workspaces", {
                "workspace_id": "fictional_debt_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "statements": [
                    {"statement_id": "statement_001", "account_key": "account_001", "creditor_label": "Fictional creditor", "period_label": "Fictional period A", "reported_balance": "fictional balance A", "responsibility_assertion": "reviewer-entered assertion", "payment_note": "fictional payment", "missing_period": False, "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    {"statement_id": "statement_002", "account_key": "account_001", "creditor_label": "Fictional creditor", "period_label": "Fictional period B", "reported_balance": "fictional balance B", "responsibility_assertion": "reviewer-entered assertion", "payment_note": "", "missing_period": True, "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                ],
            })
            debt = dict(debt_response.get("workspace") or {})
            debt_source = shared.request(helper, "GET", base_url, "/api/debt-reconciliation-workspaces/fictional_debt_001/statements/statement_001/source")

            settlement_response = shared.request(helper, "POST", base_url, "/api/settlement-scenario-comparisons", {
                "comparison_id": "fictional_settlement_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "scenarios": [
                    {"scenario_id": "scenario_a", "label": "Fictional option A", "schedules": ["Fictional schedule"], "property": [], "support": [], "implementation": [], "unresolved_terms": ["Fictional unresolved term"], "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    {"scenario_id": "scenario_b", "label": "Fictional option B", "schedules": [], "property": ["Fictional property term"], "support": [], "implementation": [], "unresolved_terms": [], "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                ],
            })
            settlement = dict(settlement_response.get("comparison") or {})
            settlement_source = shared.request(helper, "GET", base_url, "/api/settlement-scenario-comparisons/fictional_settlement_001/scenarios/scenario_a/source")

            feasibility_response = shared.request(helper, "POST", base_url, "/api/implementation-feasibility-reviews", {
                "review_id": "fictional_feasibility_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "clauses": [
                    {"clause_id": "clause_001", "topic": "schedule", "text": "Exchange at a reasonable time TBD.", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                    {"clause_id": "clause_002", "topic": "schedule", "text": "Exchange on 2026-07-04.", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}},
                ],
            })
            feasibility = dict(feasibility_response.get("review") or {})
            feasibility_source = shared.request(helper, "GET", base_url, "/api/implementation-feasibility-reviews/fictional_feasibility_001/clauses/clause_001/source")

            communication_response = shared.request(helper, "POST", base_url, "/api/communication-plans", {
                "plan_id": "fictional_communication_001", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True,
                "terms": [{"term_id": "term_001", "topic": "exchange", "text": "Fictional neutral exchange term"}],
                "source_refs": [{"record_id": "REC-DOCX", "source_hash": record_hash}],
            })
            communication = dict(communication_response.get("plan") or {})
            communication_source = shared.request(helper, "GET", base_url, "/api/communication-plans/fictional_communication_001/sources/REC-DOCX")

            compliance_response = shared.request(helper, "POST", base_url, "/api/compliance-logs", {
                "log_id": "fictional_compliance_001", "reviewer_safe_id": "reviewer_fictional_001", "term_id": "fictional_term_001", "event_id": "event_001", "date_candidate": "2026-07-04", "text": "Fictional observation", "event_state": "observation", "event_source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash}, "user_confirmed": True,
            })
            compliance = dict(compliance_response.get("log") or {})
            compliance_source = shared.request(helper, "GET", base_url, "/api/compliance-logs/fictional_compliance_001/event-source")

            source_statuses = {
                "schedule": procedure._source_status(helper, base_url, str((schedule_source.get("source") or {}).get("source_token") or "")),
                "order_calendar": procedure._source_status(helper, base_url, str((order_source.get("source") or {}).get("source_token") or "")),
                "financial": procedure._source_status(helper, base_url, str((financial_source.get("source") or {}).get("source_token") or "")),
                "asset": procedure._source_status(helper, base_url, str((asset_source.get("source") or {}).get("source_token") or "")),
                "debt": procedure._source_status(helper, base_url, str((debt_source.get("source") or {}).get("source_token") or "")),
                "settlement": procedure._source_status(helper, base_url, str((settlement_source.get("source") or {}).get("source_token") or "")),
                "feasibility": procedure._source_status(helper, base_url, str((feasibility_source.get("source") or {}).get("source_token") or "")),
                "communication": procedure._source_status(helper, base_url, str((communication_source.get("source") or {}).get("source_token") or "")),
                "compliance": procedure._source_status(helper, base_url, str((compliance_source.get("source") or {}).get("source_token") or "")),
            }
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_statuses = {
                "schedule": procedure._status(helper, base_url, "/api/parenting-schedule/simulations-v2/fictional_schedule_001"),
                "order_calendar": procedure._status(helper, base_url, "/api/calendar/order-term-extractions/fictional_order_calendar_001"),
                "financial": procedure._status(helper, base_url, "/api/financial-affidavit-workspaces/fictional_financial_001"),
                "asset": procedure._status(helper, base_url, "/api/asset-tracing-ledgers/fictional_asset_001"),
                "debt": procedure._status(helper, base_url, "/api/debt-reconciliation-workspaces/fictional_debt_001"),
                "settlement": procedure._status(helper, base_url, "/api/settlement-scenario-comparisons/fictional_settlement_001"),
                "feasibility": procedure._status(helper, base_url, "/api/implementation-feasibility-reviews/fictional_feasibility_001"),
                "communication": procedure._status(helper, base_url, "/api/communication-plans/fictional_communication_001"),
                "compliance": procedure._status(helper, base_url, "/api/compliance-logs/fictional_compliance_001"),
            }
            network = monitor.stop()
            monitor = None
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "shipped_production_ui_entries_present": ui_status == 200 and all(value in workbench_js for value in (
                    "Parenting schedule simulation", "/api/parenting-schedule/simulations-v2", "Order-to-calendar candidate", "/api/calendar/order-term-extractions", "Child-support worksheet inputs", "/api/child-support-worksheets", "Financial affidavit review", "/api/financial-affidavit-workspaces", "Asset tracing ledger", "/api/asset-tracing-ledgers", "Debt reconciliation", "/api/debt-reconciliation-workspaces", "Settlement scenario comparator", "/api/settlement-scenario-comparisons", "Implementation feasibility review", "/api/implementation-feasibility-reviews", "Communication plan", "/api/communication-plans", "Compliance log", "/api/compliance-logs",
                )),
                "parenting_schedule_is_neutral_review_only": schedule.get("recommendation") == "not_available" and schedule.get("filing_ready") is False and bool(schedule.get("date_overlaps")),
                "order_calendar_is_local_review_candidate": (order_candidate.get("candidate_event") or {}).get("calendar_account_write") is False and order_candidate.get("review_required") is True and order_candidate.get("filing_ready") is False,
                "child_support_fails_closed_without_current_authority": child_support_status in {400, 409, 422} and str(child_support_error.get("detail") or "") in {"child_support_current_authority_required", "child_support_authority_unavailable"},
                "financial_asset_debt_remain_non_determinative": financial.get("totals") == "not_calculated" and financial.get("affidavit_completion") == "not_available" and assets.get("characterization") == "not_determined" and debt.get("balance") == "not_determined" and debt.get("responsibility") == "not_determined",
                "settlement_feasibility_communication_compliance_remain_review_only": settlement.get("recommendation") == "not_available" and feasibility.get("validity") == "not_determined" and communication.get("agreement_status") == "not_determined" and communication.get("safety_status") == "not_determined" and compliance.get("compliance") == "not_determined" and (compliance.get("event") or {}).get("state") == "observation",
                "private_source_drill_downs_reopen": all(value == 200 for value in source_statuses.values()),
                "encrypted_review_sidecars": all((
                    _ciphertext(matter, "33_PARENTING_SCHEDULE/schedule.json.enc", "Fictional calendar A"),
                    _ciphertext(matter, "22_CALENDAR_REVIEW/order-term-extractions/extractions.json.enc", "Fictional calendar candidate"),
                    _ciphertext(matter, "36_FINANCIAL_REVIEW/affidavit-workspaces/workspaces.json.enc", "fictional amount A"),
                    _ciphertext(matter, "36_FINANCIAL_REVIEW/asset-tracing/ledgers.json.enc", "Reviewer-entered transfer note"),
                    _ciphertext(matter, "36_FINANCIAL_REVIEW/debt-reconciliation/workspaces.json.enc", "fictional balance A"),
                    _ciphertext(matter, "35_NEGOTIATION/settlement-scenarios/comparisons.json.enc", "Fictional property term"),
                    _ciphertext(matter, "35_NEGOTIATION/implementation-feasibility/reviews.json.enc", "reasonable time"),
                    _ciphertext(matter, "35_NEGOTIATION/communication-plans/plans.json.enc", "neutral exchange"),
                    _ciphertext(matter, "21_ORDER_INTELLIGENCE/compliance-log/events.json.enc", "Fictional observation"),
                )),
                "cross_matter_access_denied": switched.get("status") == "ok" and all(value == 404 for value in cross_statuses.values()),
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "source_hash": record_hash, "authority_source_id": authority_source_id, "source_drill_down_statuses": source_statuses,
                "cross_matter_statuses": cross_statuses, "child_support_status": child_support_status,
                "child_support_safe_code": str(child_support_error.get("detail") or ""), "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"family_finance_exception:{type(exc).__name__}"]
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
        runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True),
        authority_root=args.authority_root.resolve(strict=True), authority_source_id=str(args.authority_source_id),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
