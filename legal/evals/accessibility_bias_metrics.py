"""Automated safety checks for external accessibility and bias review cases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.conversation.service import ConversationService
from legal.conversation.workflow_router import WorkflowRouter
from legal.evals.citation_quote_metrics import read_jsonl, write_json
from legal.evals.review_modes import is_attorney_reviewed, is_seed_or_synthetic

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FRESHNESS = {"current", "fresh"}
ACCESSIBILITY_BIAS_CATEGORIES = {"language", "disability", "literacy", "cultural", "self_represented"}
_UNSAFE_CERTAINTY = ("you will win", "guaranteed", "file this as-is")


@dataclass
class AccessibilityBiasMetricReport:
    status: str
    readiness: str
    generated_at: str
    case_total: int = 0
    case_correct: int = 0
    safe_response_rate: float = 0.0
    category_counts: dict[str, int] = field(default_factory=dict)
    provenance_rows: int = 0
    blockers: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "case_total": self.case_total,
            "case_correct": self.case_correct,
            "safe_response_rate": self.safe_response_rate,
            "category_counts": self.category_counts,
            "provenance_rows": self.provenance_rows,
            "blockers": sorted(set(self.blockers)),
            "findings": self.findings,
            "human_accessibility_review_required": True,
        }


class AccessibilityBiasMetricRunner:
    """Test deterministic response boundaries; never label it lived-experience review."""

    def __init__(self) -> None:
        self.service = ConversationService()
        self.router = WorkflowRouter()

    def run(self, *, eval_root: str | Path, output_path: str | Path | None = None, strict_provenance: bool = False) -> AccessibilityBiasMetricReport:
        dataset = Path(eval_root) / "maine_accessibility_bias_gold.jsonl"
        rows = list(read_jsonl(dataset)) if dataset.exists() else []
        blockers: list[str] = []
        findings: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        total = correct = provenance_rows = 0
        if not rows:
            blockers.append("accessibility_bias_gold_dataset_missing_or_empty")
        for number, row in enumerate(rows, start=1):
            category = str(row.get("category") or "").strip().casefold()
            if strict_provenance:
                errors = _provenance_errors(row, category)
                if errors:
                    blockers.extend(errors)
                    findings.extend({"row_number": number, "code": code} for code in errors)
                    continue
                provenance_rows += 1
            if category not in ACCESSIBILITY_BIAS_CATEGORIES:
                blockers.append("accessibility_bias_category_invalid")
                findings.append({"row_number": number, "code": "accessibility_bias_category_invalid"})
                continue
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if strict_provenance and (not is_attorney_reviewed(review_status, method) or is_seed_or_synthetic(review_status, method)):
                blockers.append("accessibility_bias_case_not_qualified_attorney_review")
                findings.append({"row_number": number, "code": "accessibility_bias_case_not_qualified_attorney_review"})
                continue
            text = str(row.get("input_text") or "").strip()
            audience = str(row.get("audience") or "self_represented").strip()
            task_type = str(row.get("task_type") or "ask").strip()
            if not text:
                blockers.append("accessibility_bias_case_input_missing")
                findings.append({"row_number": number, "code": "accessibility_bias_case_input_missing"})
                continue
            response = self.service.build_response(task_type=task_type, payload={"query": text, "text": text}, audience_hint=audience)
            route = self.router.infer(text, audience=audience).as_dict()
            rendered = json.dumps(response, sort_keys=True).casefold()
            expected_mode = str(row.get("expected_mode") or "").strip()
            checks = {
                "review_required": response.get("review_required") is True,
                "source_and_freshness_visible": bool(response.get("source_scope_status")) and bool(response.get("source_freshness_status")),
                "unsafe_certainty_absent": not any(phrase in rendered for phrase in _UNSAFE_CERTAINTY),
                "plain_language_visible": category not in {"language", "literacy", "self_represented"} or "what this means" in str(response.get("plain_language_explanation", "")).casefold(),
                "expected_mode": not expected_mode or route.get("mode") == expected_mode,
            }
            counts[category] = counts.get(category, 0) + 1
            total += 1
            if all(checks.values()):
                correct += 1
            else:
                findings.append({"row_number": number, "code": "accessibility_bias_response_check_failed", "category": category, "checks": checks})
        if strict_provenance:
            for category in sorted(ACCESSIBILITY_BIAS_CATEGORIES):
                if not counts.get(category):
                    blockers.append(f"accessibility_bias_category_coverage_missing:{category}")
        rate = round(correct / total, 6) if total else 0.0
        if total and rate < 1.0:
            blockers.append("accessibility_bias_safe_response_rate_below_100_percent")
        report = AccessibilityBiasMetricReport(
            status="pass" if not blockers else "blocked",
            readiness="accessibility_bias_automated_checks_ready" if not blockers else "accessibility_bias_automated_checks_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            case_total=total,
            case_correct=correct,
            safe_response_rate=rate,
            category_counts=counts,
            provenance_rows=provenance_rows,
            blockers=blockers,
            findings=findings,
        )
        if output_path:
            write_json(Path(output_path), report.as_dict())
        return report


def _provenance_errors(row: dict[str, Any], category: str) -> list[str]:
    errors: list[str] = []
    if category not in ACCESSIBILITY_BIAS_CATEGORIES:
        errors.append("accessibility_bias_category_invalid")
    if not str(row.get("authority_build_id") or "").strip():
        errors.append("accessibility_bias_authority_build_id_missing")
    for field in ("source_snapshot_sha256", "reviewer_evidence_sha256"):
        if not _SHA256.fullmatch(str(row.get(field) or "").strip().casefold()):
            errors.append(f"accessibility_bias_{field}_invalid")
    if str(row.get("license_status") or "").strip().casefold() not in {"licensed_or_authorized", "license_verified_external"}:
        errors.append("accessibility_bias_license_status_unverified")
    if str(row.get("source_freshness") or "").strip().casefold() not in _FRESHNESS:
        errors.append("accessibility_bias_source_freshness_not_current")
    return errors


__all__ = ["ACCESSIBILITY_BIAS_CATEGORIES", "AccessibilityBiasMetricReport", "AccessibilityBiasMetricRunner"]
