from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.evals.citation_quote_metrics import read_jsonl, write_json
from legal.evals.review_modes import (
    basis_suffix,
    is_attorney_reviewed,
    is_operator_source_backed,
    is_seed_or_synthetic,
    normalize_review_mode,
    reviewer_status_for_metric,
)
from legal.forms.intelligence import FormCatalogBuilder
from legal.verifiers.staleness_jurisdiction import FreshnessJurisdictionTreatmentChecker

SCOPE_TARGET = 1.0
FORM_FRESHNESS_TARGET = 0.99


@dataclass(frozen=True)
class StalenessJurisdictionMetricFinding:
    row_number: int | None
    dataset: str
    code: str
    message: str
    source_id: str | None = None
    expected_status: str | None = None
    actual_status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "dataset": self.dataset,
            "code": self.code,
            "message": self.message,
            "source_id": self.source_id,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
        }


@dataclass
class StalenessJurisdictionMetricReport:
    status: str
    readiness: str
    generated_at: str
    scope_dataset: str
    forms_dataset: str
    review_mode: str = "attorney_reviewed"
    scope_total: int = 0
    scope_correct: int = 0
    scope_verification: float = 0.0
    form_total: int = 0
    form_correct: int = 0
    form_freshness_detection: float = 0.0
    scope_attorney_reviewed_rows: int = 0
    form_attorney_reviewed_rows: int = 0
    scope_operator_source_backed_rows: int = 0
    form_operator_source_backed_rows: int = 0
    scope_seed_or_synthetic_rows: int = 0
    form_seed_or_synthetic_rows: int = 0
    blockers: list[str] = field(default_factory=list)
    findings: list[StalenessJurisdictionMetricFinding] = field(default_factory=list)
    release_metric_measurements: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "scope_dataset": self.scope_dataset,
            "forms_dataset": self.forms_dataset,
            "review_mode": self.review_mode,
            "scope_total": self.scope_total,
            "scope_correct": self.scope_correct,
            "scope_verification": self.scope_verification,
            "form_total": self.form_total,
            "form_correct": self.form_correct,
            "form_freshness_detection": self.form_freshness_detection,
            "scope_attorney_reviewed_rows": self.scope_attorney_reviewed_rows,
            "form_attorney_reviewed_rows": self.form_attorney_reviewed_rows,
            "scope_operator_source_backed_rows": self.scope_operator_source_backed_rows,
            "form_operator_source_backed_rows": self.form_operator_source_backed_rows,
            "scope_seed_or_synthetic_rows": self.scope_seed_or_synthetic_rows,
            "form_seed_or_synthetic_rows": self.form_seed_or_synthetic_rows,
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
            "release_metric_measurements": self.release_metric_measurements,
        }


class StalenessJurisdictionMetricRunner:
    """Measure Pass 31 stale-law, jurisdiction, treatment, and form freshness gates.

    This is fail-closed for production evidence. Empty datasets, seed rows, rows that
    are not reviewed for the selected review mode, wrong-jurisdiction misses, current-law
    claims from stale/unknown sources, and stale/unknown form versions block readiness.
    """

    def __init__(
        self,
        *,
        scope_target: float = SCOPE_TARGET,
        form_freshness_target: float = FORM_FRESHNESS_TARGET,
        require_review: bool = True,
        review_mode: str = "attorney_reviewed",
    ) -> None:
        self.scope_target = scope_target
        self.form_freshness_target = form_freshness_target
        self.require_review = require_review
        self.review_mode = normalize_review_mode(review_mode)
        self.scope_checker = FreshnessJurisdictionTreatmentChecker()
        self.form_builder = FormCatalogBuilder()

    def run(
        self,
        *,
        eval_root: str | Path,
        output_path: str | Path | None = None,
        measurement_output_path: str | Path | None = None,
    ) -> StalenessJurisdictionMetricReport:
        eval_path = Path(eval_root)
        scope_path = eval_path / "maine_staleness_jurisdiction_gold.jsonl"
        forms_path = eval_path / "maine_forms_freshness_gold.jsonl"
        scope_rows = list(read_jsonl(scope_path)) if scope_path.exists() else []
        form_rows = list(read_jsonl(forms_path)) if forms_path.exists() else []
        generated_at = datetime.now(timezone.utc).isoformat()
        blockers: list[str] = []
        findings: list[StalenessJurisdictionMetricFinding] = []

        if not scope_rows:
            blockers.append("staleness_jurisdiction_gold_dataset_missing_or_empty")
            findings.append(StalenessJurisdictionMetricFinding(None, scope_path.name, "dataset_missing_or_empty", str(scope_path)))
        if not form_rows:
            blockers.append("forms_freshness_gold_dataset_missing_or_empty")
            findings.append(StalenessJurisdictionMetricFinding(None, forms_path.name, "dataset_missing_or_empty", str(forms_path)))

        scope_result = self._measure_scope(scope_rows, findings, blockers)
        form_result = self._measure_forms(form_rows, findings, blockers)
        scope_rate = _ratio(scope_result["correct"], scope_result["total"])
        form_rate = _ratio(form_result["correct"], form_result["total"])

        if scope_result["total"] and scope_rate < self.scope_target:
            blockers.append("scope_verification_below_100_percent")
        if form_result["total"] and form_rate < self.form_freshness_target:
            blockers.append("form_freshness_detection_below_99_percent")

        review_key = "attorney_reviewed" if self.review_mode == "attorney_reviewed" else "operator_source_backed"
        scope_reviewed = (
            scope_result["total"] > 0
            and scope_result[review_key] == scope_result["total"]
            and scope_result["seed_or_synthetic"] == 0
        )
        form_reviewed = (
            form_result["total"] > 0
            and form_result[review_key] == form_result["total"]
            and form_result["seed_or_synthetic"] == 0
        )
        if self.require_review:
            if not scope_reviewed:
                blockers.append(f"scope_gold_not_fully_{self.review_mode}")
            if not form_reviewed:
                blockers.append(f"forms_gold_not_fully_{self.review_mode}")
            if scope_result["seed_or_synthetic"]:
                blockers.append("scope_gold_contains_seed_or_synthetic_rows")
            if form_result["seed_or_synthetic"]:
                blockers.append("forms_gold_contains_seed_or_synthetic_rows")

        release_metrics = [
            {
                "name": "scope_verification",
                "value": scope_rate,
                "sample_size": scope_result["total"],
                "basis": f"pass31_scope_metric_runner_over_{basis_suffix(self.review_mode)}_gold",
                "attorney_reviewed": self.review_mode == "attorney_reviewed" and scope_reviewed,
                "operator_source_backed": self.review_mode == "operator_source_backed" and scope_reviewed,
                "reviewer_status": reviewer_status_for_metric(review_mode=self.review_mode, reviewed=scope_reviewed),
                "source_dataset": "maine_staleness_jurisdiction_gold.jsonl",
                "minimum_sample_size": scope_result["total"],
                "operator": ">=",
                "target": self.scope_target,
            },
            {
                "name": "form_freshness_detection",
                "value": form_rate,
                "sample_size": form_result["total"],
                "basis": f"pass31_form_metric_runner_over_{basis_suffix(self.review_mode)}_gold",
                "attorney_reviewed": self.review_mode == "attorney_reviewed" and form_reviewed,
                "operator_source_backed": self.review_mode == "operator_source_backed" and form_reviewed,
                "reviewer_status": reviewer_status_for_metric(review_mode=self.review_mode, reviewed=form_reviewed),
                "source_dataset": "maine_forms_freshness_gold.jsonl",
                "minimum_sample_size": form_result["total"],
                "operator": ">=",
                "target": self.form_freshness_target,
            },
        ]
        report = StalenessJurisdictionMetricReport(
            status="pass" if not blockers else "blocked",
            readiness="pass31_staleness_jurisdiction_metrics_ready" if not blockers else "pass31_staleness_jurisdiction_metrics_blocked",
            generated_at=generated_at,
            scope_dataset=str(scope_path),
            forms_dataset=str(forms_path),
            review_mode=self.review_mode,
            scope_total=scope_result["total"],
            scope_correct=scope_result["correct"],
            scope_verification=scope_rate,
            form_total=form_result["total"],
            form_correct=form_result["correct"],
            form_freshness_detection=form_rate,
            scope_attorney_reviewed_rows=scope_result["attorney_reviewed"],
            form_attorney_reviewed_rows=form_result["attorney_reviewed"],
            scope_operator_source_backed_rows=scope_result["operator_source_backed"],
            form_operator_source_backed_rows=form_result["operator_source_backed"],
            scope_seed_or_synthetic_rows=scope_result["seed_or_synthetic"],
            form_seed_or_synthetic_rows=form_result["seed_or_synthetic"],
            blockers=blockers,
            findings=findings,
            release_metric_measurements=release_metrics,
        )
        if output_path:
            write_json(Path(output_path), report.as_dict())
        if measurement_output_path:
            write_json(
                Path(measurement_output_path),
                {
                    "schema_version": "release_metric_measurements_v1",
                    "generated_at": generated_at,
                    "readiness": "partial_pass31_staleness_jurisdiction_metric_file",
                    "metrics": release_metrics,
                },
            )
        return report

    def _measure_scope(
        self,
        rows: list[dict[str, Any]],
        findings: list[StalenessJurisdictionMetricFinding],
        blockers: list[str],
    ) -> dict[str, int]:
        total = correct = attorney_reviewed = operator_source_backed = seed_or_synthetic = 0
        for idx, row in enumerate(rows, start=1):
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if is_attorney_reviewed(review_status, method):
                attorney_reviewed += 1
            if is_operator_source_backed(row, review_status, method):
                operator_source_backed += 1
            if is_seed_or_synthetic(review_status, method):
                seed_or_synthetic += 1

            text = _first_text(row, "answer_text", "text", "text_span", "claim")
            sources = _source_metadata_from_row(row)
            expected = _expected_scope_status(row)
            if not text and expected != "current_law_claim_without_sources":
                findings.append(StalenessJurisdictionMetricFinding(idx, "maine_staleness_jurisdiction_gold.jsonl", "scope_row_missing_text", "row needs answer_text/text/text_span/claim"))
                blockers.append("scope_row_missing_text")
                continue
            if not sources and expected != "current_law_claim_without_sources":
                findings.append(StalenessJurisdictionMetricFinding(idx, "maine_staleness_jurisdiction_gold.jsonl", "scope_row_missing_source_metadata", "row needs source_metadata/source row fields"))
                blockers.append("scope_row_missing_source_metadata")
                continue

            total += 1
            report = self.scope_checker.check(text=text, source_metadata=sources, expected_jurisdiction=str(row.get("expected_jurisdiction") or "maine"))
            actual = _actual_scope_status(report)
            if _scope_status_matches(expected, actual, report):
                correct += 1
            else:
                source_id = _first_source_id(sources)
                findings.append(
                    StalenessJurisdictionMetricFinding(
                        idx,
                        "maine_staleness_jurisdiction_gold.jsonl",
                        "scope_status_mismatch",
                        f"expected_status={expected}; actual_status={actual}; blockers={report.get('blockers', [])}; warnings={report.get('warnings', [])}",
                        source_id=source_id,
                        expected_status=expected,
                        actual_status=actual,
                    )
                )
        return {
            "total": total,
            "correct": correct,
            "attorney_reviewed": attorney_reviewed,
            "operator_source_backed": operator_source_backed,
            "seed_or_synthetic": seed_or_synthetic,
        }

    def _measure_forms(
        self,
        rows: list[dict[str, Any]],
        findings: list[StalenessJurisdictionMetricFinding],
        blockers: list[str],
    ) -> dict[str, int]:
        total = correct = attorney_reviewed = operator_source_backed = seed_or_synthetic = 0
        for idx, row in enumerate(rows, start=1):
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if is_attorney_reviewed(review_status, method):
                attorney_reviewed += 1
            if is_operator_source_backed(row, review_status, method):
                operator_source_backed += 1
            if is_seed_or_synthetic(review_status, method):
                seed_or_synthetic += 1
            form_id = str(row.get("form_id") or "").strip()
            if not form_id:
                findings.append(StalenessJurisdictionMetricFinding(idx, "maine_forms_freshness_gold.jsonl", "form_id_missing", "row needs form_id"))
                blockers.append("form_row_missing_form_id")
                continue
            total += 1
            current_versions = _current_versions_for_row(row, form_id)
            record = {
                "source_id": row.get("source_id") or form_id,
                "source_class": row.get("source_class") or "court_form",
                "form_id": form_id,
                "title": row.get("title") or row.get("text_span") or form_id,
                "text": _first_text(row, "source_text", "text", "text_span", "title"),
                "version_date": row.get("version_date") or row.get("detected_version_date"),
                "citation": row.get("citation") or form_id,
                "issue_labels": row.get("issue_labels") or row.get("expected_issue_labels"),
            }
            catalog = self.form_builder.build_catalog([record], current_versions=current_versions)
            actual = catalog.entries[0].freshness_status if catalog.entries else "unknown"
            expected = _expected_form_status(row)
            if _form_status_matches(expected, actual):
                correct += 1
            else:
                findings.append(
                    StalenessJurisdictionMetricFinding(
                        idx,
                        "maine_forms_freshness_gold.jsonl",
                        "form_freshness_mismatch",
                        f"expected_freshness_status={expected}; actual_status={actual}",
                        source_id=str(row.get("source_id") or form_id),
                        expected_status=expected,
                        actual_status=actual,
                    )
                )
        return {
            "total": total,
            "correct": correct,
            "attorney_reviewed": attorney_reviewed,
            "operator_source_backed": operator_source_backed,
            "seed_or_synthetic": seed_or_synthetic,
        }


def _source_metadata_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = row.get("source_metadata") or row.get("sources")
    if isinstance(metadata, dict):
        # A mapping of id -> metadata or a single source row.
        if any(isinstance(value, dict) for value in metadata.values()):
            sources = []
            for source_id, value in metadata.items():
                if isinstance(value, dict):
                    source = dict(value)
                    source.setdefault("source_id", source_id)
                    sources.append(source)
            if sources:
                return sources
        return [dict(metadata)]
    if isinstance(metadata, list):
        return [dict(item) for item in metadata if isinstance(item, dict)]
    source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
    if not source_id:
        return []
    return [
        {
            "source_id": source_id,
            "source_class": row.get("source_class") or row.get("authority_kind") or "unknown",
            "jurisdiction": row.get("source_jurisdiction") or row.get("jurisdiction") or "unknown",
            "freshness_status": row.get("freshness_status") or "unknown",
            "authority_status": row.get("authority_status") or row.get("status") or "stale_unknown",
            "negative_treatment_status": row.get("negative_treatment_status"),
            "form_version_status": row.get("form_version_status") or row.get("version_status"),
            "form_id": row.get("form_id"),
            "citation": row.get("citation"),
        }
    ]


def _actual_scope_status(report: dict[str, Any]) -> str:
    blockers = list(report.get("blockers") or [])
    if "current_law_claim_without_sources" in blockers:
        return "current_law_claim_without_sources"
    checks = list(report.get("checks") or [])
    if checks:
        blocking = [check for check in checks if check.get("blocker")]
        if blocking:
            return str(blocking[0].get("status") or "blocked")
        non_verified = [check for check in checks if check.get("status") != "verified_scope"]
        if non_verified:
            return str(non_verified[0].get("status") or "warning")
    return "verified_scope"


def _expected_scope_status(row: dict[str, Any]) -> str:
    raw = row.get("expected_status") or row.get("expected_scope_status") or row.get("label") or "verified_scope"
    if isinstance(raw, list):
        value = " ".join(str(item) for item in raw).lower()
    else:
        value = str(raw).lower()
    for status in (
        "current_law_claim_without_sources",
        "jurisdiction_mismatch",
        "stale_or_unknown_freshness",
        "negative_treatment_unknown",
        "form_freshness_not_verified",
        "verified_scope",
    ):
        if status in value:
            return status
    if "freshness" in value and ("stale" in value or "unknown" in value):
        return "stale_or_unknown_freshness"
    if "jurisdiction" in value:
        return "jurisdiction_mismatch"
    if "negative" in value or "treatment" in value:
        return "negative_treatment_unknown"
    if "form" in value:
        return "form_freshness_not_verified"
    if "pass" in value or "valid" in value or "source_backed" in value:
        return "verified_scope"
    return value.strip() or "verified_scope"


def _scope_status_matches(expected: str, actual: str, report: dict[str, Any]) -> bool:
    if expected == actual:
        return True
    if expected == "verified_scope":
        return not report.get("blockers") and actual == "verified_scope"
    if expected == "stale_or_unknown_freshness":
        return actual == "stale_or_unknown_freshness" or any(str(item).startswith("stale_or_unknown_freshness:") for item in report.get("blockers", []))
    if expected == "jurisdiction_mismatch":
        return actual == "jurisdiction_mismatch" or any(str(item).startswith("jurisdiction_mismatch:") for item in report.get("blockers", []))
    if expected == "negative_treatment_unknown":
        return actual == "negative_treatment_unknown" or any(str(item).startswith("negative_treatment_unknown:") for item in report.get("blockers", []))
    if expected == "form_freshness_not_verified":
        return actual == "form_freshness_not_verified" or any(str(item).startswith("form_freshness_not_verified:") for item in report.get("blockers", []))
    return False


def _expected_form_status(row: dict[str, Any]) -> str:
    raw = row.get("expected_freshness_status") or row.get("expected_status") or row.get("label") or "current"
    if isinstance(raw, list):
        value = " ".join(str(item) for item in raw).lower()
    else:
        value = str(raw).lower()
    if "known_current" in value or "current" in value or value == "known":
        return "current"
    if "stale" in value:
        return "stale"
    if "unknown" in value:
        return "unknown"
    return value.strip() or "current"


def _form_status_matches(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    if expected == "known":
        return actual in {"current", "stale"}
    if expected == "not_current":
        return actual in {"stale", "unknown"}
    return False


def _current_versions_for_row(row: dict[str, Any], form_id: str) -> dict[str, str]:
    raw = row.get("current_versions")
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items() if value}
    current = row.get("current_version_date") or row.get("expected_current_version") or row.get("current_version")
    if current:
        return {form_id: str(current)}
    expected = _expected_form_status(row)
    version = row.get("version_date") or row.get("detected_version_date")
    if expected == "current" and version:
        return {form_id: str(version)}
    return {}


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_source_id(sources: list[dict[str, Any]]) -> str | None:
    for source in sources:
        source_id = source.get("source_id") or source.get("record_id")
        if source_id:
            return str(source_id)
    return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
