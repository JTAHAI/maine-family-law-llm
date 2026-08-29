from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.citation_quote_metrics import load_source_texts, read_jsonl, write_json
from legal.evals.review_modes import (
    basis_suffix,
    is_attorney_reviewed,
    is_operator_source_backed,
    is_seed_or_synthetic,
    normalize_review_mode,
    reviewer_status_for_metric,
)
from legal.verifiers.claim_support_verifier import ClaimSupportVerifier

CLAIM_SUPPORT_TARGET = 0.95
BLOCKING_CLAIM_STATUSES = {"partially_supported", "unsupported", "contradicted", "stale", "jurisdiction_mismatch", "not_verifiable"}
SUPPORTED_EXPECTATIONS = {"supported", "support", "valid", "valid_citation", "found", "true", "yes"}
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FRESHNESS = {"current", "fresh"}
# ``unknown`` is the gold-label spelling for a deliberately non-verifiable
# proposition.  The verifier's stable machine result for that outcome is
# ``not_verifiable``; keeping both explicit prevents a negative result from
# being quietly relabeled as unsupported support.
REQUIRED_CLAIM_STATUS_LABELS = {
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "stale",
    "jurisdiction_mismatch",
    "unknown",
}


@dataclass(frozen=True)
class ClaimSupportMetricFinding:
    row_number: int | None
    dataset: str
    code: str
    message: str
    source_id: str | None = None
    claim: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "dataset": self.dataset,
            "code": self.code,
            "message": self.message,
            "source_id": self.source_id,
            "claim": self.claim,
        }


@dataclass
class ClaimSupportMetricReport:
    status: str
    readiness: str
    generated_at: str
    claim_dataset: str
    review_mode: str = "attorney_reviewed"
    source_text_basis: list[str] = field(default_factory=list)
    claim_total: int = 0
    claim_correct: int = 0
    citation_support: float = 0.0
    claim_attorney_reviewed_rows: int = 0
    claim_operator_source_backed_rows: int = 0
    claim_seed_or_synthetic_rows: int = 0
    blocking_claim_statuses_seen: int = 0
    expected_status_counts: dict[str, int] = field(default_factory=dict)
    actual_status_counts: dict[str, int] = field(default_factory=dict)
    status_metrics: dict[str, dict[str, int | float]] = field(default_factory=dict)
    provenance_rows: int = 0
    issue_counts: dict[str, int] = field(default_factory=dict)
    freshness_counts: dict[str, int] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    findings: list[ClaimSupportMetricFinding] = field(default_factory=list)
    release_metric_measurements: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "claim_dataset": self.claim_dataset,
            "review_mode": self.review_mode,
            "source_text_basis": self.source_text_basis,
            "claim_total": self.claim_total,
            "claim_correct": self.claim_correct,
            "citation_support": self.citation_support,
            "claim_attorney_reviewed_rows": self.claim_attorney_reviewed_rows,
            "claim_operator_source_backed_rows": self.claim_operator_source_backed_rows,
            "claim_seed_or_synthetic_rows": self.claim_seed_or_synthetic_rows,
            "blocking_claim_statuses_seen": self.blocking_claim_statuses_seen,
            "expected_status_counts": self.expected_status_counts,
            "actual_status_counts": self.actual_status_counts,
            "status_metrics": self.status_metrics,
            "provenance_rows": self.provenance_rows,
            "issue_counts": self.issue_counts,
            "freshness_counts": self.freshness_counts,
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
            "release_metric_measurements": self.release_metric_measurements,
        }


class ClaimSupportMetricRunner:
    """Measure Pass 30 claim-support verification against external attorney-reviewed gold.

    The release metric emitted here is ``citation_support``. It is fail-closed:
    empty datasets, seed rows, missing source text, non-attorney-reviewed rows, and
    unsupported claim mismatches block readiness instead of yielding optimistic GA evidence.
    """

    def __init__(
        self,
        *,
        target: float = CLAIM_SUPPORT_TARGET,
        require_attorney_review: bool = True,
        review_mode: str = "attorney_reviewed",
    ) -> None:
        self.target = target
        self.require_attorney_review = require_attorney_review
        self.review_mode = normalize_review_mode(review_mode)
        self.verifier = ClaimSupportVerifier()

    def run(
        self,
        *,
        eval_root: str | Path,
        source_text_jsonl: str | Path | None = None,
        parsed_authority_root: str | Path | None = None,
        output_path: str | Path | None = None,
        measurement_output_path: str | Path | None = None,
        strict_provenance: bool = False,
    ) -> ClaimSupportMetricReport:
        eval_path = Path(eval_root)
        claim_path = eval_path / "maine_citation_validity_gold.jsonl"
        source_texts, source_basis = load_source_texts(
            source_text_jsonl=source_text_jsonl,
            parsed_authority_root=parsed_authority_root,
        )
        rows = list(read_jsonl(claim_path)) if claim_path.exists() else []
        generated_at = datetime.now(timezone.utc).isoformat()
        blockers: list[str] = []
        findings: list[ClaimSupportMetricFinding] = []

        if not rows:
            blockers.append("claim_support_gold_dataset_missing_or_empty")
            findings.append(ClaimSupportMetricFinding(None, claim_path.name, "dataset_missing_or_empty", str(claim_path)))
        if not source_texts:
            blockers.append("source_texts_missing")
            findings.append(
                ClaimSupportMetricFinding(
                    None,
                    "source_texts",
                    "source_texts_missing",
                    "Provide --source-text-jsonl or --parsed-authority-root with source_id/record_id + text rows.",
                )
            )

        result = self._measure(rows, source_texts, findings, blockers, strict_provenance=strict_provenance)
        support_rate = _ratio(result["correct"], result["total"])
        if result["total"] and support_rate < self.target:
            blockers.append("citation_support_below_95_percent")
        review_key = "attorney_reviewed" if self.review_mode == "attorney_reviewed" else "operator_source_backed"
        reviewed = (
            result["total"] > 0
            and result[review_key] == result["total"]
            and result["seed_or_synthetic"] == 0
        )
        if self.require_attorney_review:
            if not reviewed:
                blockers.append(f"claim_support_gold_not_fully_{self.review_mode}")
            if result["seed_or_synthetic"]:
                blockers.append("claim_support_gold_contains_seed_or_synthetic_rows")
        if strict_provenance:
            for label in sorted(REQUIRED_CLAIM_STATUS_LABELS):
                if not result["expected_status_counts"].get(label, 0):
                    blockers.append(f"claim_status_coverage_missing:{label}")

        release_metrics = [
            {
                "name": "citation_support",
                "value": support_rate,
                "sample_size": result["total"],
                "basis": f"pass30_claim_support_metric_runner_over_{basis_suffix(self.review_mode)}_gold",
                "attorney_reviewed": self.review_mode == "attorney_reviewed" and reviewed,
                "operator_source_backed": self.review_mode == "operator_source_backed" and reviewed,
                "reviewer_status": reviewer_status_for_metric(review_mode=self.review_mode, reviewed=reviewed),
                "source_dataset": "maine_citation_validity_gold.jsonl",
                "minimum_sample_size": result["total"],
                "operator": ">=",
                "target": self.target,
            }
        ]
        report = ClaimSupportMetricReport(
            status="pass" if not blockers else "blocked",
            readiness="pass30_claim_support_metrics_ready" if not blockers else "pass30_claim_support_metrics_blocked",
            generated_at=generated_at,
            claim_dataset=str(claim_path),
            review_mode=self.review_mode,
            source_text_basis=source_basis,
            claim_total=result["total"],
            claim_correct=result["correct"],
            citation_support=support_rate,
            claim_attorney_reviewed_rows=result["attorney_reviewed"],
            claim_operator_source_backed_rows=result["operator_source_backed"],
            claim_seed_or_synthetic_rows=result["seed_or_synthetic"],
            blocking_claim_statuses_seen=result["blocking_statuses"],
            expected_status_counts=result["expected_status_counts"],
            actual_status_counts=result["actual_status_counts"],
            status_metrics=result["status_metrics"],
            provenance_rows=result["provenance_rows"],
            issue_counts=result["issue_counts"],
            freshness_counts=result["freshness_counts"],
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
                    "readiness": "partial_pass30_claim_support_metric_file",
                    "metrics": release_metrics,
                },
            )
        return report

    def _measure(
        self,
        rows: list[dict[str, Any]],
        source_texts: dict[str, str],
        findings: list[ClaimSupportMetricFinding],
        blockers: list[str],
        *,
        strict_provenance: bool,
    ) -> dict[str, Any]:
        total = correct = attorney_reviewed = operator_source_backed = seed_or_synthetic = blocking_statuses = 0
        provenance_rows = 0
        expected_status_counts: dict[str, int] = {}
        actual_status_counts: dict[str, int] = {}
        status_correct: dict[str, int] = {}
        issue_counts: dict[str, int] = {}
        freshness_counts: dict[str, int] = {}
        for idx, row in enumerate(rows, start=1):
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if _is_attorney_reviewed(review_status, method):
                attorney_reviewed += 1
            if _is_operator_source_backed(row, review_status, method):
                operator_source_backed += 1
            if _is_seed_or_synthetic(review_status, method):
                seed_or_synthetic += 1

            expected = _expected_claim_status(row)
            if strict_provenance:
                errors = _strict_provenance_errors(row, expected)
                if errors:
                    for code in errors:
                        findings.append(
                            ClaimSupportMetricFinding(
                                idx,
                                "maine_citation_validity_gold.jsonl",
                                code,
                                "strict claim benchmark row provenance is incomplete or invalid",
                                source_id=_source_ids(row)[0] if _source_ids(row) else None,
                            )
                        )
                    blockers.extend(errors)
                    continue
                provenance_rows += 1
                for label in _labels(row):
                    issue_counts[label] = issue_counts.get(label, 0) + 1
                freshness = str(row.get("source_freshness") or "").strip().casefold()
                freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1

            claim = _first_text(row, "claim", "legal_claim", "assertion", "answer_claim", "text_span")
            source_ids = _source_ids(row)
            evidence_chunks = _evidence_chunks(row, source_ids, source_texts)
            if not claim or not evidence_chunks:
                findings.append(
                    ClaimSupportMetricFinding(
                        idx,
                        "maine_citation_validity_gold.jsonl",
                        "claim_support_row_missing_claim_or_evidence",
                        "row needs claim/legal_claim/assertion/text_span plus source text from source_id/source_ids/evidence_text",
                        source_id=source_ids[0] if source_ids else None,
                        claim=claim or None,
                    )
                )
                blockers.append("claim_support_row_missing_claim_or_evidence")
                continue

            total += 1
            expected_status_counts[expected] = expected_status_counts.get(expected, 0) + 1
            source_jurisdictions = _row_values(row, "source_jurisdiction", "source_jurisdictions", "jurisdiction")
            authority_statuses = _row_values(row, "authority_status", "authority_statuses", "source_authority_status")
            actual = self.verifier.verify_claim(
                claim,
                evidence_chunks,
                source_ids=source_ids,
                source_jurisdictions=source_jurisdictions,
                authority_statuses=authority_statuses,
                expected_jurisdiction=str(row.get("expected_jurisdiction") or "maine"),
            )
            actual_status = actual.status
            actual_status_counts[actual_status] = actual_status_counts.get(actual_status, 0) + 1
            if actual_status in BLOCKING_CLAIM_STATUSES:
                blocking_statuses += 1
            if _status_matches(expected, actual_status):
                correct += 1
                status_correct[expected] = status_correct.get(expected, 0) + 1
            else:
                findings.append(
                    ClaimSupportMetricFinding(
                        idx,
                        "maine_citation_validity_gold.jsonl",
                        "claim_support_mismatch",
                        f"expected_status={expected}; actual_status={actual_status}; confidence={actual.confidence}",
                        source_id=source_ids[0] if source_ids else None,
                        claim=claim,
                    )
                )
        status_metrics = {
            label: {
                "sample_size": expected_status_counts.get(label, 0),
                "correct": status_correct.get(label, 0),
                "accuracy": _ratio(status_correct.get(label, 0), expected_status_counts.get(label, 0)),
            }
            for label in sorted(REQUIRED_CLAIM_STATUS_LABELS)
        }
        return {
            "total": total,
            "correct": correct,
            "attorney_reviewed": attorney_reviewed,
            "operator_source_backed": operator_source_backed,
            "seed_or_synthetic": seed_or_synthetic,
            "blocking_statuses": blocking_statuses,
            "expected_status_counts": expected_status_counts,
            "actual_status_counts": actual_status_counts,
            "status_metrics": status_metrics,
            "provenance_rows": provenance_rows,
            "issue_counts": issue_counts,
            "freshness_counts": freshness_counts,
        }


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _source_ids(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    raw = row.get("source_ids")
    if isinstance(raw, list):
        values.extend(str(item) for item in raw if str(item).strip())
    elif raw:
        values.extend(item.strip() for item in str(raw).split(",") if item.strip())
    for key in ("source_id", "record_id", "expected_source_id"):
        value = row.get(key)
        if value and str(value).strip():
            values.append(str(value).strip())
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _evidence_chunks(row: dict[str, Any], source_ids: list[str], source_texts: dict[str, str]) -> list[str]:
    chunks: list[str] = []
    for key in ("evidence_text", "evidence_span", "supporting_text", "source_text"):
        value = row.get(key)
        if isinstance(value, list):
            chunks.extend(str(item) for item in value if str(item).strip())
        elif value and str(value).strip():
            chunks.append(str(value).strip())
    for source_id in source_ids:
        text = source_texts.get(source_id)
        if text:
            chunks.append(text)
    return chunks


def _row_values(row: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if str(item).strip())
        elif value and str(value).strip():
            values.extend(item.strip() for item in str(value).split(",") if item.strip())
    return values


def _expected_claim_status(row: dict[str, Any]) -> str:
    raw = row.get("expected_status") or row.get("expected") or row.get("label") or row.get("claim_status") or "supported"
    if isinstance(raw, list):
        text = " ".join(str(item) for item in raw)
    else:
        text = str(raw)
    lowered = text.lower()
    for status in ("jurisdiction_mismatch", "partially_supported", "not_verifiable", "unknown", "contradicted", "unsupported", "stale"):
        if status in lowered:
            return "unknown" if status in {"unknown", "not_verifiable"} else status
    if any(marker in lowered for marker in SUPPORTED_EXPECTATIONS):
        return "supported"
    return lowered.strip() or "supported"


def _status_matches(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    if expected == "supported":
        return actual == "supported"
    if expected == "unknown":
        return actual == "not_verifiable"
    if expected == "blocked":
        return actual in BLOCKING_CLAIM_STATUSES
    return False


def _is_attorney_reviewed(review_status: str, method: str) -> bool:
    return is_attorney_reviewed(review_status, method)


def _is_operator_source_backed(row: dict[str, Any], review_status: str, method: str) -> bool:
    return is_operator_source_backed(row, review_status, method)


def _is_seed_or_synthetic(review_status: str, method: str) -> bool:
    return is_seed_or_synthetic(review_status, method)


def _labels(row: dict[str, Any]) -> list[str]:
    raw = row.get("issue_labels") or row.get("issue_label") or []
    values = raw if isinstance(raw, list) else str(raw).split(",")
    return sorted({str(value).strip().casefold() for value in values if str(value).strip()})


def _strict_provenance_errors(row: dict[str, Any], expected: str) -> list[str]:
    """Return line-safe failures for the release-only claim benchmark contract.

    The metric runner has a long-lived fixture mode.  The production benchmark
    calls this strict mode so a locally invented row cannot masquerade as a
    current, licensed, externally reviewed legal measurement.
    """

    errors: list[str] = []
    if expected not in REQUIRED_CLAIM_STATUS_LABELS:
        errors.append("claim_status_label_invalid")
    if not _labels(row):
        errors.append("claim_issue_labels_missing")
    if not str(row.get("authority_build_id") or "").strip():
        errors.append("claim_authority_build_id_missing")
    if not _SHA256.fullmatch(str(row.get("source_snapshot_sha256") or "").strip().casefold()):
        errors.append("claim_source_snapshot_sha256_invalid")
    if not _SHA256.fullmatch(str(row.get("reviewer_evidence_sha256") or "").strip().casefold()):
        errors.append("claim_reviewer_evidence_sha256_invalid")
    if str(row.get("license_status") or "").strip().casefold() not in {
        "licensed_or_authorized",
        "license_verified_external",
    }:
        errors.append("claim_license_status_unverified")
    if str(row.get("source_freshness") or "").strip().casefold() not in _FRESHNESS:
        errors.append("claim_source_freshness_not_current")
    return errors


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
