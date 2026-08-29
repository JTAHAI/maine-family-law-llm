from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

MANDATORY_CHECKS = [
    "authority_verified",
    "citations_resolved",
    "quotes_found",
    "legal_claims_supported",
    "facts_mapped_to_evidence",
    "procedure_posture_checked",
    "forms_current",
    "privacy_review_complete",
    "human_review_complete",
]

LEGACY_CHECK_ALIASES = {
    "citations_resolved": ["citations_verified"],
    "quotes_found": ["quote_spans_verified"],
    "legal_claims_supported": ["claims_supported", "citation_support_verified"],
    "facts_mapped_to_evidence": ["facts_verified"],
    "forms_current": ["form_freshness_verified"],
}

PASS7_MANDATORY_CHECKS = [
    "citation_support_verified",
    "claims_supported",
    "jurisdiction_verified",
    "form_freshness_verified",
    "facts_verified",
]

BLOCKING_VERIFICATION_PREFIXES = (
    "citation_not_found",
    "quote_span_not_found",
    "claim_unsupported",
    "claim_partially_supported",
    "claim_contradicted",
    "claim_stale",
    "claim_jurisdiction_mismatch",
    "claim_not_verifiable",
    "authority_not_verified",
    "stale_or_unknown_freshness",
    "jurisdiction_mismatch",
    "negative_treatment_unknown",
    "form_freshness_not_verified",
    "current_law_claim_without_sources",
    "verifier_exception",
    "verification_exception",
    "verifier_unavailable",
)

VERIFIED_AUTHORITY_STATUSES = {
    "verified_official_maine",
    "verified_maine_law_court",
    "verified_federal",
    "verified_public_api",
}

QUOTE_PASS_STATUSES = {"exact", "fuzzy", "quote_exact_match", "quote_fuzzy_match", "found"}
CLAIM_PASS_STATUSES = {"supported"}


class FilingReadyGate:
    """Final export gate for review-required Maine family-law work product.

    The gate never treats an attorney override as a pass. Overrides are logged in
    the immutable gate report while filing-ready export remains blocked unless
    every mandatory check is independently satisfied.
    """

    gate_version = "pass38-filing-ready-hardening-v1"

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        blockers: list[str] = []
        mandatory_results: dict[str, bool] = {}

        derived = self._derive_checks(payload)
        for check in MANDATORY_CHECKS:
            passed = self._check_value(payload, check, derived)
            mandatory_results[check] = passed
            if not passed:
                blockers.append(check)

        # Keep compatibility with the earlier verifier-intelligence gates.
        for check in PASS7_MANDATORY_CHECKS:
            if check in payload and not payload.get(check, False):
                blockers.append(check)

        verification_report = payload.get("verification_report") or {}
        # A verifier report's ``blockers`` collection is authoritative.  An
        # unrecognized blocker must fail closed instead of being silently
        # downgraded because a caller supplied optimistic summary booleans.
        for blocker in verification_report.get("blockers", []):
            value = str(blocker).strip()
            if value:
                blockers.append(value)

        blockers.extend(derived["blockers"])
        blockers.extend(str(item) for item in (payload.get("workflow_blockers") or []) if str(item))
        blockers.extend(str(item) for item in (payload.get("review_annotation_blockers") or []) if str(item))
        procedure_report = payload.get("procedure_posture_report") or {}
        blockers.extend(str(item) for item in (procedure_report.get("blockers") or []) if str(item))
        forms_report = payload.get("forms_report") or {}
        blockers.extend(str(item) for item in (forms_report.get("blockers") or []) if str(item))
        findings_report = payload.get("findings_review") or payload.get("findings_report") or {}
        blockers.extend(str(item) for item in (findings_report.get("blockers") or []) if str(item))
        privacy_report = payload.get("privacy_report") or payload.get("privacy_review") or {}
        blockers.extend(str(item) for item in (privacy_report.get("blockers") or []) if str(item))

        if payload.get("review_required", True) and not payload.get("human_review_complete", False):
            blockers.append("human_review_complete")

        blockers = sorted(set(blockers))
        override_record = self._build_override_record(payload, blockers)
        filing_ready = len(blockers) == 0
        export_status = "allowed" if filing_ready else "blocked"
        if override_record and not filing_ready:
            export_status = "blocked_override_logged"

        gate_report = {
            "gate_version": self.gate_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mandatory_checks": mandatory_results,
            "blockers": blockers,
            "attorney_override": override_record,
            "filing_ready": filing_ready,
            "export_status": export_status,
        }
        gate_report["immutable_report_hash"] = self._hash_report(gate_report)
        blocker_panel = {
            "panel_title": "Filing gate blockers",
            "review_required": True,
            "filing_ready": filing_ready,
            "export_status": export_status,
            "blockers": blockers,
            "immutable_report_hash": gate_report["immutable_report_hash"],
        }

        return {
            "filing_ready": filing_ready,
            "blockers": blockers,
            "review_required": not payload.get("human_review_complete", False),
            "export_status": export_status,
            "mandatory_checks": mandatory_results,
            "gate_report": gate_report,
            "immutable_gate_report": gate_report,
            "attorney_override_logged": bool(override_record),
            "blocked_export_explanation": blockers,
            "blocker_panel": blocker_panel,
        }

    def _check_value(self, payload: dict[str, Any], check: str, derived: dict[str, Any]) -> bool:
        if check in payload:
            return bool(payload.get(check)) and bool(derived["checks"].get(check, False))
        for alias in LEGACY_CHECK_ALIASES.get(check, []):
            if alias in payload and not payload.get(alias):
                return False
            if alias in payload and payload.get(alias):
                return bool(derived["checks"].get(check, False))
        return bool(derived["checks"].get(check, False))

    def _derive_checks(self, payload: dict[str, Any]) -> dict[str, Any]:
        blockers: list[str] = []
        checks = {
            "authority_verified": self._authority_verified(payload, blockers),
            "citations_resolved": self._citations_resolved(payload, blockers),
            "quotes_found": self._quotes_found(payload, blockers),
            "legal_claims_supported": self._legal_claims_supported(payload, blockers),
            "facts_mapped_to_evidence": self._facts_mapped(payload, blockers),
            "procedure_posture_checked": self._procedure_checked(payload, blockers),
            "forms_current": self._forms_current(payload, blockers),
            "privacy_review_complete": self._privacy_reviewed(payload, blockers),
            "human_review_complete": bool(payload.get("human_review_complete", False)),
        }
        return {"checks": checks, "blockers": blockers}

    def _authority_verified(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = bool(payload.get("authority_verified")) if "authority_verified" in payload else None
        authorities = payload.get("authority_matrix") or payload.get("authorities") or []
        if not authorities:
            if declared is not None:
                return declared
            blockers.append("authority_matrix_missing")
            return False
        ok = True
        for item in authorities:
            status = str(item.get("authority_status", item.get("status", "")))
            if status not in VERIFIED_AUTHORITY_STATUSES:
                blockers.append(f"authority_not_verified:{item.get('source_id') or item.get('citation') or 'unknown'}")
                ok = False
        return ok and declared is not False

    def _citations_resolved(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = None
        if "citations_resolved" in payload or "citations_verified" in payload:
            declared = bool(payload.get("citations_resolved", payload.get("citations_verified")))
        report = payload.get("citation_report") or []
        if not report:
            if declared is not None:
                return declared
            blockers.append("citation_report_missing")
            return False
        ok = True
        for row in report:
            status = str(row.get("status", row.get("resolution_status", ""))).lower()
            if status not in {"resolved", "verified", "found", "supported"}:
                blockers.append(f"citation_unresolved:{row.get('citation') or row.get('source_id') or 'unknown'}")
                ok = False
        return ok and declared is not False

    def _quotes_found(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = None
        if "quotes_found" in payload or "quote_spans_verified" in payload:
            declared = bool(payload.get("quotes_found", payload.get("quote_spans_verified")))
        report = payload.get("quote_report") or []
        if not report:
            if declared is not None:
                return declared
            blockers.append("quote_report_missing")
            return False
        ok = True
        for row in report:
            status = str(row.get("match_type", row.get("status", ""))).lower()
            start = row.get("start_offset", row.get("start"))
            end = row.get("end_offset", row.get("end"))
            if status not in QUOTE_PASS_STATUSES or start is None or end is None:
                blockers.append(f"quote_span_not_found:{row.get('source_id') or row.get('citation') or 'unknown'}")
                ok = False
        return ok and declared is not False

    def _legal_claims_supported(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = None
        if "legal_claims_supported" in payload or "claims_supported" in payload:
            declared = bool(payload.get("legal_claims_supported", payload.get("claims_supported")))
        report = payload.get("claim_support_report") or payload.get("claim_report") or {}
        claims = report.get("claims", []) if isinstance(report, dict) else report
        if not isinstance(claims, list):
            blockers.append("claim_support_report_invalid")
            return False
        if not claims:
            if declared is not None:
                return declared
            blockers.append("claim_support_report_missing")
            return False
        ok = True
        for row in claims:
            if not isinstance(row, dict):
                blockers.append("claim_support_report_invalid")
                ok = False
                continue
            status = str(row.get("support_status", row.get("status", ""))).lower()
            if status not in CLAIM_PASS_STATUSES or row.get("supported") is False:
                blockers.append(f"claim_not_supported:{row.get('claim_id') or row.get('claim') or 'unknown'}")
                ok = False
        return ok and declared is not False

    def _facts_mapped(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = None
        if "facts_mapped_to_evidence" in payload or "facts_verified" in payload:
            declared = bool(payload.get("facts_mapped_to_evidence", payload.get("facts_verified")))
        mappings = payload.get("fact_to_evidence_map") or payload.get("evidence_map") or []
        if not mappings:
            if declared is not None:
                return declared
            blockers.append("fact_to_evidence_map_missing")
            return False
        ok = True
        for row in mappings:
            source_ids = row.get("source_document_ids") or row.get("evidence_document_ids") or []
            source_id = row.get("source_document_id") or row.get("evidence_document_id")
            span = row.get("span") or row.get("source_span") or {}
            has_span = (span.get("start_offset") is not None and span.get("end_offset") is not None) or (
                row.get("start_offset") is not None and row.get("end_offset") is not None
            )
            if not (source_id or source_ids) or not has_span:
                blockers.append(f"fact_not_mapped:{row.get('fact_id') or row.get('fact') or 'unknown'}")
                ok = False
            support_status = str(row.get("support_status") or "supported").strip().lower()
            if support_status != "supported" or row.get("supported") is False:
                blockers.append(
                    f"fact_not_supported:{row.get('fact_id') or row.get('fact') or 'unknown'}:{support_status or 'unknown'}"
                )
                ok = False
            if bool(row.get("allegation_promoted_to_finding")):
                blockers.append(
                    f"allegation_promoted_to_finding:{row.get('fact_id') or row.get('fact') or 'unknown'}"
                )
                ok = False
        return ok and declared is not False

    def _procedure_checked(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = bool(payload.get("procedure_posture_checked")) if "procedure_posture_checked" in payload else None
        report = payload.get("procedure_posture_report") or payload.get("posture_report") or {}
        if report.get("blockers"):
            return False
        if report.get("status") in {"checked", "pass", "verified"} or report.get("procedural_posture"):
            return declared is not False
        if declared is not None:
            return declared
        blockers.append("procedure_posture_report_missing")
        return False

    def _forms_current(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        declared = None
        if "forms_current" in payload or "form_freshness_verified" in payload:
            declared = bool(payload.get("forms_current", payload.get("form_freshness_verified")))
        forms_report = payload.get("forms_report") or payload.get("form_freshness_report") or {}
        stale_forms = forms_report.get("stale_forms", [])
        unknown_forms = forms_report.get("unknown_forms", [])
        if forms_report and not stale_forms and not unknown_forms and not forms_report.get("blockers"):
            return declared is not False
        if stale_forms:
            blockers.extend(f"stale_form:{form_id}" for form_id in stale_forms)
        if unknown_forms:
            blockers.extend(f"unknown_form_freshness:{form_id}" for form_id in unknown_forms)
        if not forms_report and declared is not None:
            return declared
        if not forms_report:
            blockers.append("forms_freshness_report_missing")
        return False

    def _privacy_reviewed(self, payload: dict[str, Any], blockers: list[str]) -> bool:
        complete = payload.get("privacy_review_complete") is True
        report = payload.get("privacy_report") or payload.get("privacy_review") or {}
        if report.get("blockers"):
            return False
        if not complete:
            blockers.append("privacy_review_incomplete")
            return False
        return True

    def _build_override_record(self, payload: dict[str, Any], blockers: list[str]) -> dict[str, Any] | None:
        override = payload.get("attorney_override") or payload.get("override")
        if not override:
            return None
        return {
            "requested": True,
            "requested_by": override.get("requested_by", override.get("attorney_id", "unknown_attorney")),
            "reason": override.get("reason", "not_provided"),
            "requested_at": override.get("requested_at", datetime.now(timezone.utc).isoformat()),
            "blockers_at_override": blockers,
            "effect": "logged_only_export_remains_blocked_unless_all_gate_checks_pass",
        }

    def _hash_report(self, report: dict[str, Any]) -> str:
        stable = {k: v for k, v in report.items() if k != "immutable_report_hash"}
        blob = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()
