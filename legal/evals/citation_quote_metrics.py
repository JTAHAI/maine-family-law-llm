from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.verifiers.citation_parser import extract_citations
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier
from legal.evals.review_modes import (
    basis_suffix,
    is_attorney_reviewed,
    is_operator_source_backed,
    is_seed_or_synthetic,
    normalize_review_mode,
    reviewer_status_for_metric,
)

CITATION_TARGET = 0.99
QUOTE_TARGET = 0.97
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FRESHNESS = {"current", "fresh"}
REQUIRED_QUOTE_DECISIONS = {"exact", "normalized", "fuzzy_review_required", "mismatch", "not_found"}


@dataclass(frozen=True)
class VerifierMetricFinding:
    row_number: int | None
    dataset: str
    code: str
    message: str
    source_id: str | None = None
    citation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "dataset": self.dataset,
            "code": self.code,
            "message": self.message,
            "source_id": self.source_id,
            "citation": self.citation,
        }


@dataclass
class VerifierMetricReport:
    status: str
    readiness: str
    generated_at: str
    citation_dataset: str
    quote_dataset: str
    authority_index_path: str
    review_mode: str = "attorney_reviewed"
    source_text_basis: list[str] = field(default_factory=list)
    citation_total: int = 0
    citation_correct: int = 0
    citation_existence: float = 0.0
    quote_total: int = 0
    quote_correct: int = 0
    quote_span_verification: float = 0.0
    citation_attorney_reviewed_rows: int = 0
    quote_attorney_reviewed_rows: int = 0
    citation_operator_source_backed_rows: int = 0
    quote_operator_source_backed_rows: int = 0
    citation_seed_or_synthetic_rows: int = 0
    quote_seed_or_synthetic_rows: int = 0
    quote_expected_decision_counts: dict[str, int] = field(default_factory=dict)
    quote_actual_decision_counts: dict[str, int] = field(default_factory=dict)
    quote_decision_metrics: dict[str, dict[str, int | float]] = field(default_factory=dict)
    quote_provenance_rows: int = 0
    quote_parser_variant_counts: dict[str, int] = field(default_factory=dict)
    quote_issue_counts: dict[str, int] = field(default_factory=dict)
    quote_freshness_counts: dict[str, int] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    findings: list[VerifierMetricFinding] = field(default_factory=list)
    release_metric_measurements: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "citation_dataset": self.citation_dataset,
            "quote_dataset": self.quote_dataset,
            "authority_index_path": self.authority_index_path,
            "review_mode": self.review_mode,
            "source_text_basis": self.source_text_basis,
            "citation_total": self.citation_total,
            "citation_correct": self.citation_correct,
            "citation_existence": self.citation_existence,
            "quote_total": self.quote_total,
            "quote_correct": self.quote_correct,
            "quote_span_verification": self.quote_span_verification,
            "citation_attorney_reviewed_rows": self.citation_attorney_reviewed_rows,
            "quote_attorney_reviewed_rows": self.quote_attorney_reviewed_rows,
            "citation_operator_source_backed_rows": self.citation_operator_source_backed_rows,
            "quote_operator_source_backed_rows": self.quote_operator_source_backed_rows,
            "citation_seed_or_synthetic_rows": self.citation_seed_or_synthetic_rows,
            "quote_seed_or_synthetic_rows": self.quote_seed_or_synthetic_rows,
            "quote_expected_decision_counts": self.quote_expected_decision_counts,
            "quote_actual_decision_counts": self.quote_actual_decision_counts,
            "quote_decision_metrics": self.quote_decision_metrics,
            "quote_provenance_rows": self.quote_provenance_rows,
            "quote_parser_variant_counts": self.quote_parser_variant_counts,
            "quote_issue_counts": self.quote_issue_counts,
            "quote_freshness_counts": self.quote_freshness_counts,
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
            "release_metric_measurements": self.release_metric_measurements,
        }


class CitationQuoteVerifierMetricRunner:
    """Measure Pass 29 citation/quote verifier behavior against external gold rows.

    This runner is deliberately fail-closed for GA use: rows must be attorney-reviewed,
    seed/synthetic rows are counted and blocked when ``require_attorney_review`` is true,
    and missing source text or missing authority index rows produce blockers instead of
    optimistic measurements.
    """

    def __init__(
        self,
        *,
        citation_target: float = CITATION_TARGET,
        quote_target: float = QUOTE_TARGET,
        require_attorney_review: bool = True,
        review_mode: str = "attorney_reviewed",
    ) -> None:
        self.citation_target = citation_target
        self.quote_target = quote_target
        self.require_attorney_review = require_attorney_review
        self.review_mode = normalize_review_mode(review_mode)

    def run(
        self,
        *,
        eval_root: str | Path,
        authority_index_path: str | Path,
        source_text_jsonl: str | Path | None = None,
        parsed_authority_root: str | Path | None = None,
        output_path: str | Path | None = None,
        measurement_output_path: str | Path | None = None,
        strict_provenance: bool = False,
    ) -> VerifierMetricReport:
        eval_path = Path(eval_root)
        citation_path = eval_path / "maine_citation_validity_gold.jsonl"
        quote_path = eval_path / "maine_quote_span_gold.jsonl"
        source_texts, source_basis = load_source_texts(
            source_text_jsonl=source_text_jsonl,
            parsed_authority_root=parsed_authority_root,
        )
        authority_index = load_authority_index(authority_index_path)
        generated_at = datetime.now(timezone.utc).isoformat()
        findings: list[VerifierMetricFinding] = []
        blockers: list[str] = []

        citation_rows = list(read_jsonl(citation_path)) if citation_path.exists() else []
        quote_rows = list(read_jsonl(quote_path)) if quote_path.exists() else []
        if not citation_rows:
            blockers.append("citation_gold_dataset_missing_or_empty")
            findings.append(
                VerifierMetricFinding(None, citation_path.name, "dataset_missing_or_empty", str(citation_path))
            )
        if not quote_rows:
            blockers.append("quote_gold_dataset_missing_or_empty")
            findings.append(
                VerifierMetricFinding(None, quote_path.name, "dataset_missing_or_empty", str(quote_path))
            )
        if not source_texts:
            blockers.append("source_texts_missing")
            findings.append(
                VerifierMetricFinding(
                    None,
                    "source_texts",
                    "source_texts_missing",
                    "Provide --source-text-jsonl or --parsed-authority-root with source_id/record_id + text rows.",
                )
            )

        citation_result = self._measure_citations(citation_rows, authority_index, findings, blockers, strict_provenance=strict_provenance)
        quote_result = self._measure_quotes(quote_rows, source_texts, findings, blockers, strict_provenance=strict_provenance)

        citation_rate = _ratio(citation_result["correct"], citation_result["total"])
        quote_rate = _ratio(quote_result["correct"], quote_result["total"])
        if citation_result["total"] and citation_rate < self.citation_target:
            blockers.append("citation_existence_below_99_percent")
        if quote_result["total"] and quote_rate < self.quote_target:
            blockers.append("quote_span_verification_below_97_percent")
        citation_review_key = "attorney_reviewed" if self.review_mode == "attorney_reviewed" else "operator_source_backed"
        quote_review_key = citation_review_key
        citation_reviewed = (
            citation_result["total"] > 0
            and citation_result[citation_review_key] == citation_result["total"]
            and citation_result["seed_or_synthetic"] == 0
        )
        quote_reviewed = (
            quote_result["total"] > 0
            and quote_result[quote_review_key] == quote_result["total"]
            and quote_result["seed_or_synthetic"] == 0
        )
        if self.require_attorney_review:
            if not citation_reviewed:
                blockers.append(f"citation_gold_not_fully_{self.review_mode}")
            if not quote_reviewed:
                blockers.append(f"quote_gold_not_fully_{self.review_mode}")
            if citation_result["seed_or_synthetic"]:
                blockers.append("citation_gold_contains_seed_or_synthetic_rows")
            if quote_result["seed_or_synthetic"]:
                blockers.append("quote_gold_contains_seed_or_synthetic_rows")
        if strict_provenance:
            for decision in sorted(REQUIRED_QUOTE_DECISIONS):
                if not quote_result["expected_decision_counts"].get(decision, 0):
                    blockers.append(f"quote_decision_coverage_missing:{decision}")

        release_metrics = [
            {
                "name": "citation_existence",
                "value": citation_rate,
                "sample_size": citation_result["total"],
                "basis": f"pass29_verifier_metric_runner_over_{basis_suffix(self.review_mode)}_gold",
                "attorney_reviewed": self.review_mode == "attorney_reviewed" and citation_reviewed,
                "operator_source_backed": self.review_mode == "operator_source_backed" and citation_reviewed,
                "reviewer_status": reviewer_status_for_metric(review_mode=self.review_mode, reviewed=citation_reviewed),
                "source_dataset": "maine_citation_validity_gold.jsonl",
                "minimum_sample_size": citation_result["total"],
                "operator": ">=",
                "target": self.citation_target,
            },
            {
                "name": "quote_span_verification",
                "value": quote_rate,
                "sample_size": quote_result["total"],
                "basis": f"pass29_verifier_metric_runner_over_{basis_suffix(self.review_mode)}_gold",
                "attorney_reviewed": self.review_mode == "attorney_reviewed" and quote_reviewed,
                "operator_source_backed": self.review_mode == "operator_source_backed" and quote_reviewed,
                "reviewer_status": reviewer_status_for_metric(review_mode=self.review_mode, reviewed=quote_reviewed),
                "source_dataset": "maine_quote_span_gold.jsonl",
                "minimum_sample_size": quote_result["total"],
                "operator": ">=",
                "target": self.quote_target,
            },
        ]
        report = VerifierMetricReport(
            status="pass" if not blockers else "blocked",
            readiness="pass29_verifier_metrics_ready" if not blockers else "pass29_verifier_metrics_blocked",
            generated_at=generated_at,
            citation_dataset=str(citation_path),
            quote_dataset=str(quote_path),
            authority_index_path=str(Path(authority_index_path)),
            review_mode=self.review_mode,
            source_text_basis=source_basis,
            citation_total=citation_result["total"],
            citation_correct=citation_result["correct"],
            citation_existence=citation_rate,
            quote_total=quote_result["total"],
            quote_correct=quote_result["correct"],
            quote_span_verification=quote_rate,
            citation_attorney_reviewed_rows=citation_result["attorney_reviewed"],
            quote_attorney_reviewed_rows=quote_result["attorney_reviewed"],
            citation_operator_source_backed_rows=citation_result["operator_source_backed"],
            quote_operator_source_backed_rows=quote_result["operator_source_backed"],
            citation_seed_or_synthetic_rows=citation_result["seed_or_synthetic"],
            quote_seed_or_synthetic_rows=quote_result["seed_or_synthetic"],
            quote_expected_decision_counts=quote_result["expected_decision_counts"],
            quote_actual_decision_counts=quote_result["actual_decision_counts"],
            quote_decision_metrics=quote_result["decision_metrics"],
            quote_provenance_rows=quote_result["provenance_rows"],
            quote_parser_variant_counts=quote_result["parser_variant_counts"],
            quote_issue_counts=quote_result["issue_counts"],
            quote_freshness_counts=quote_result["freshness_counts"],
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
                    "readiness": "partial_pass29_metrics_only",
                    "metrics": release_metrics,
                },
            )
        return report

    def _measure_citations(
        self,
        rows: list[dict[str, Any]],
        authority_index: SourceAuthorityIndex,
        findings: list[VerifierMetricFinding],
        blockers: list[str],
        *,
        strict_provenance: bool,
    ) -> dict[str, int]:
        total = correct = attorney_reviewed = operator_source_backed = seed_or_synthetic = 0
        for idx, row in enumerate(rows, start=1):
            if strict_provenance:
                errors = _strict_provenance_errors(row, require_parser_variant=False)
                if errors:
                    for code in errors:
                        findings.append(VerifierMetricFinding(idx, "maine_citation_validity_gold.jsonl", code, "strict verifier benchmark row provenance is incomplete or invalid"))
                    blockers.extend(errors)
                    continue
            citation_text = _first_text(row, "citation", "text_span", "raw_citation", "normalized_citation")
            expected_found = _expected_found(row)
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if _is_attorney_reviewed(review_status, method):
                attorney_reviewed += 1
            if _is_operator_source_backed(row, review_status, method):
                operator_source_backed += 1
            if _is_seed_or_synthetic(review_status, method):
                seed_or_synthetic += 1
            if not citation_text:
                findings.append(
                    VerifierMetricFinding(idx, "maine_citation_validity_gold.jsonl", "citation_text_missing", "row has no citation/text_span")
                )
                blockers.append("citation_row_missing_text")
                continue
            total += 1
            citations = extract_citations(citation_text)
            if not citations:
                found = False
                findings.append(
                    VerifierMetricFinding(
                        idx,
                        "maine_citation_validity_gold.jsonl",
                        "citation_parse_failed",
                        "no supported citation parsed from row text",
                        citation=citation_text,
                    )
                )
            else:
                resolutions = [authority_index.resolve(citation) for citation in citations]
                found = any(resolution.status == "found" for resolution in resolutions)
            if found == expected_found:
                correct += 1
            else:
                findings.append(
                    VerifierMetricFinding(
                        idx,
                        "maine_citation_validity_gold.jsonl",
                        "citation_existence_mismatch",
                        f"expected_found={expected_found}; actual_found={found}",
                        source_id=str(row.get("source_id") or "") or None,
                        citation=citation_text,
                    )
                )
        return {
            "total": total,
            "correct": correct,
            "attorney_reviewed": attorney_reviewed,
            "operator_source_backed": operator_source_backed,
            "seed_or_synthetic": seed_or_synthetic,
        }

    def _measure_quotes(
        self,
        rows: list[dict[str, Any]],
        source_texts: dict[str, str],
        findings: list[VerifierMetricFinding],
        blockers: list[str],
        *,
        strict_provenance: bool,
    ) -> dict[str, Any]:
        verifier = QuoteSpanVerifier()
        total = correct = attorney_reviewed = operator_source_backed = seed_or_synthetic = 0
        provenance_rows = 0
        expected_decision_counts: dict[str, int] = {}
        actual_decision_counts: dict[str, int] = {}
        decision_correct: dict[str, int] = {}
        parser_variant_counts: dict[str, int] = {}
        issue_counts: dict[str, int] = {}
        freshness_counts: dict[str, int] = {}
        for idx, row in enumerate(rows, start=1):
            source_id = str(row.get("source_id") or row.get("record_id") or "")
            quote = _first_text(row, "quote", "quoted_text", "text_span")
            expected_found = _expected_found(row)
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if _is_attorney_reviewed(review_status, method):
                attorney_reviewed += 1
            if _is_operator_source_backed(row, review_status, method):
                operator_source_backed += 1
            if _is_seed_or_synthetic(review_status, method):
                seed_or_synthetic += 1
            expected_decision = _expected_quote_decision(row)
            if strict_provenance:
                errors = _strict_provenance_errors(row, require_parser_variant=True)
                if errors:
                    for code in errors:
                        findings.append(VerifierMetricFinding(idx, "maine_quote_span_gold.jsonl", code, "strict quote benchmark row provenance is incomplete or invalid", source_id=source_id or None))
                    blockers.extend(errors)
                    continue
                provenance_rows += 1
                parser_variant = str(row.get("parser_variant") or "").strip().casefold()
                parser_variant_counts[parser_variant] = parser_variant_counts.get(parser_variant, 0) + 1
                for label in _labels(row):
                    issue_counts[label] = issue_counts.get(label, 0) + 1
                freshness = str(row.get("source_freshness") or "").strip().casefold()
                freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1
            if not source_id or not quote:
                findings.append(
                    VerifierMetricFinding(
                        idx,
                        "maine_quote_span_gold.jsonl",
                        "quote_row_missing_source_or_text",
                        "row needs source_id and quote/quoted_text/text_span",
                        source_id=source_id or None,
                    )
                )
                blockers.append("quote_row_missing_source_or_text")
                continue
            total += 1
            expected_decision_counts[expected_decision] = expected_decision_counts.get(expected_decision, 0) + 1
            source_text = source_texts.get(source_id, "")
            if not source_text:
                findings.append(
                    VerifierMetricFinding(
                        idx,
                        "maine_quote_span_gold.jsonl",
                        "quote_source_text_missing",
                        "source text was not loaded for source_id",
                        source_id=source_id,
                    )
                )
                found = False
            else:
                result = verifier.verify(source_text, quote)
                found = result["status"] in {"exact_match", "fuzzy_match", "semantic_match"} and bool(result["quote_span_found"])
                actual_decision = _actual_quote_decision(result)
                if found and (result.get("start_offset") is None or result.get("end_offset") is None):
                    findings.append(
                        VerifierMetricFinding(
                            idx,
                            "maine_quote_span_gold.jsonl",
                            "quote_offsets_missing",
                            "verified quote did not record source offsets",
                            source_id=source_id,
                        )
                    )
                    # A fuzzy/semantic result is deliberately a review queue,
                    # not a silently accepted exact span.  Strict benchmark
                    # coverage must be able to measure that state without
                    # treating lack of an exact offset as a false exact pass.
                    if not (strict_provenance and actual_decision == "fuzzy_review_required"):
                        blockers.append("quote_offsets_missing")
            if not source_text:
                actual_decision = "not_found"
            actual_decision_counts[actual_decision] = actual_decision_counts.get(actual_decision, 0) + 1
            decision_match = (not strict_provenance) or _quote_decision_matches(expected_decision, actual_decision)
            if found == expected_found and decision_match:
                correct += 1
                decision_correct[expected_decision] = decision_correct.get(expected_decision, 0) + 1
            else:
                findings.append(
                    VerifierMetricFinding(
                        idx,
                        "maine_quote_span_gold.jsonl",
                        "quote_span_mismatch",
                        f"expected_decision={expected_decision}; actual_decision={actual_decision}; expected_found={expected_found}; actual_found={found}",
                        source_id=source_id,
                    )
                )
        decision_metrics = {
            decision: {
                "sample_size": expected_decision_counts.get(decision, 0),
                "correct": decision_correct.get(decision, 0),
                "accuracy": _ratio(decision_correct.get(decision, 0), expected_decision_counts.get(decision, 0)),
            }
            for decision in sorted(REQUIRED_QUOTE_DECISIONS)
        }
        return {
            "total": total,
            "correct": correct,
            "attorney_reviewed": attorney_reviewed,
            "operator_source_backed": operator_source_backed,
            "seed_or_synthetic": seed_or_synthetic,
            "expected_decision_counts": expected_decision_counts,
            "actual_decision_counts": actual_decision_counts,
            "decision_metrics": decision_metrics,
            "provenance_rows": provenance_rows,
            "parser_variant_counts": parser_variant_counts,
            "issue_counts": issue_counts,
            "freshness_counts": freshness_counts,
        }


def load_authority_index(path: str | Path) -> SourceAuthorityIndex:
    index_path = Path(path)
    rows = list(read_jsonl(index_path)) if index_path.suffix.lower() == ".jsonl" else _load_json_rows(index_path)
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or row.get("record_id") or "")
        citation = str(row.get("normalized_citation") or row.get("citation") or "")
        kind = str(row.get("kind") or row.get("citation_kind") or "")
        if not source_id or not citation:
            continue
        if not kind:
            parsed = extract_citations(citation)
            kind = parsed[0].kind if parsed else ""
        parsed = extract_citations(citation)
        normalized = str(row.get("normalized_citation") or (parsed[0].normalized if parsed else citation))
        if kind and normalized:
            normalized_rows.append(
                {
                    "kind": kind,
                    "normalized_citation": normalized,
                    "source_id": source_id,
                    "authority_status": row.get("authority_status") or row.get("status") or "verified_official_maine",
                    "metadata": row.get("metadata") or row,
                }
            )
    return SourceAuthorityIndex.from_rows(normalized_rows)


def load_source_texts(
    *,
    source_text_jsonl: str | Path | None = None,
    parsed_authority_root: str | Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    basis: list[str] = []
    if source_text_jsonl:
        path = Path(source_text_jsonl)
        if path.exists():
            basis.append(str(path))
            for row in read_jsonl(path):
                _add_text_row(texts, row)
    if parsed_authority_root:
        root = Path(parsed_authority_root)
        if root.exists():
            basis.append(str(root))
            for path in sorted(root.rglob("*.jsonl")):
                for row in read_jsonl(path):
                    _add_text_row(texts, row)
    return texts, basis


def read_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json_rows(path: Path) -> list[Any]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "citations", "index", "sources", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _add_text_row(texts: dict[str, str], row: dict[str, Any]) -> None:
    source_id = str(row.get("source_id") or row.get("record_id") or row.get("id") or "")
    text = str(row.get("text") or row.get("source_text") or row.get("content") or "")
    if source_id and text and source_id not in texts:
        texts[source_id] = text


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _expected_found(row: dict[str, Any]) -> bool:
    expected = str(row.get("expected_decision") or row.get("expected_status") or row.get("expected") or row.get("label") or "found").lower()
    return expected in {"found", "valid", "valid_citation", "quote_span_exact", "quote_span_found", "supported", "true", "exact", "normalized", "fuzzy_review_required"}


def _expected_quote_decision(row: dict[str, Any]) -> str:
    raw = str(row.get("expected_decision") or row.get("expected_status") or row.get("expected") or row.get("label") or "exact").strip().casefold()
    aliases = {
        "exact_match": "exact",
        "quote_span_exact": "exact",
        "fuzzy_match": "fuzzy_review_required",
        "semantic_match": "fuzzy_review_required",
        "quote_span_not_found": "not_found",
        "not_verifiable": "not_found",
    }
    return aliases.get(raw, raw)


def _actual_quote_decision(result: dict[str, Any]) -> str:
    if result.get("status") == "exact_match":
        return "exact"
    if result.get("method") == "normalized_whitespace":
        return "normalized"
    if result.get("status") in {"fuzzy_match", "semantic_match"}:
        return "fuzzy_review_required"
    return "not_found"


def _quote_decision_matches(expected: str, actual: str) -> bool:
    # A source-mismatch test case is successful only when its purported quote
    # is not found in the source.  It remains separately counted so a broad
    # not-found result cannot obscure cross-source failures.
    if expected == "mismatch":
        return actual == "not_found"
    return expected == actual


def _labels(row: dict[str, Any]) -> list[str]:
    raw = row.get("issue_labels") or row.get("issue_label") or []
    values = raw if isinstance(raw, list) else str(raw).split(",")
    return sorted({str(value).strip().casefold() for value in values if str(value).strip()})


def _strict_provenance_errors(row: dict[str, Any], *, require_parser_variant: bool) -> list[str]:
    errors: list[str] = []
    if not _labels(row):
        errors.append("verifier_issue_labels_missing")
    if not str(row.get("authority_build_id") or "").strip():
        errors.append("verifier_authority_build_id_missing")
    if not _SHA256.fullmatch(str(row.get("source_snapshot_sha256") or "").strip().casefold()):
        errors.append("verifier_source_snapshot_sha256_invalid")
    if not _SHA256.fullmatch(str(row.get("reviewer_evidence_sha256") or "").strip().casefold()):
        errors.append("verifier_reviewer_evidence_sha256_invalid")
    if str(row.get("license_status") or "").strip().casefold() not in {"licensed_or_authorized", "license_verified_external"}:
        errors.append("verifier_license_status_unverified")
    if str(row.get("source_freshness") or "").strip().casefold() not in _FRESHNESS:
        errors.append("verifier_source_freshness_not_current")
    if require_parser_variant and not str(row.get("parser_variant") or "").strip():
        errors.append("quote_parser_variant_missing")
    return errors


def _is_attorney_reviewed(review_status: str, method: str) -> bool:
    return is_attorney_reviewed(review_status, method)


def _is_operator_source_backed(row: dict[str, Any], review_status: str, method: str) -> bool:
    return is_operator_source_backed(row, review_status, method)


def _is_seed_or_synthetic(review_status: str, method: str) -> bool:
    return is_seed_or_synthetic(review_status, method)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
