"""Fail-closed attorney-gold retrieval evaluation for v5.12."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from legal.evals.retrieval_metrics import summarize_ranked_retrieval

MAX_EVAL_ROWS = 5_000
MAX_QUERY_CHARS = 2_000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FRESHNESS = {"current", "fresh"}


class AttorneyRetrievalEvalError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttorneyRetrievalEvalReport:
    status: str
    dataset_sha256: str
    rows_seen: int
    attorney_reviewed_rows: int
    evaluated_rows: int
    metrics: dict[str, float]
    failures: tuple[dict[str, Any], ...]
    blockers: tuple[str, ...]
    issue_counts: dict[str, int]
    freshness_counts: dict[str, int]
    provenance_rows: int
    exact_citation_rows: int
    exact_citation_accuracy: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "attorney_gold_retrieval_eval_v1",
            "status": self.status,
            "dataset_sha256": self.dataset_sha256,
            "rows_seen": self.rows_seen,
            "attorney_reviewed_rows": self.attorney_reviewed_rows,
            "evaluated_rows": self.evaluated_rows,
            "metrics": self.metrics,
            "failures": list(self.failures),
            "blockers": list(self.blockers),
            "issue_counts": self.issue_counts,
            "freshness_counts": self.freshness_counts,
            "provenance_rows": self.provenance_rows,
            "exact_citation_rows": self.exact_citation_rows,
            "exact_citation_accuracy": self.exact_citation_accuracy,
            "pinpoint_accuracy": None,
            "pinpoint_accuracy_status": "not_measured_by_source-id_retrieval_contract",
            "basis": "attorney-reviewed external JSONL only; generated, seed, synthetic, and private-training rows excluded",
            "review_required": True,
        }


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relevant_ids(row: dict[str, Any]) -> set[str]:
    values = (
        row.get("relevant_source_ids")
        or row.get("expected_source_ids")
        or row.get("gold_source_ids")
        or row.get("source_ids")
        or []
    )
    if isinstance(values, str):
        values = [values]
    return {str(value) for value in values if str(value).strip()}


def _sha256(value: Any) -> bool:
    return bool(_SHA256.fullmatch(str(value or "").strip().casefold()))


def _labels(row: dict[str, Any]) -> list[str]:
    values = row.get("issue_labels") or row.get("issue_label") or []
    if isinstance(values, str):
        values = [values]
    return sorted({str(value).strip().casefold() for value in values if str(value).strip()})


def _strict_provenance_errors(row: dict[str, Any], *, line_number: int) -> list[str]:
    errors: list[str] = []
    if not _labels(row):
        errors.append(f"missing_issue_labels:{line_number}")
    if not str(row.get("authority_build_id") or "").strip():
        errors.append(f"missing_authority_build_id:{line_number}")
    if not _sha256(row.get("source_snapshot_sha256")):
        errors.append(f"missing_source_snapshot_sha256:{line_number}")
    if not _sha256(row.get("reviewer_evidence_sha256")):
        errors.append(f"missing_reviewer_evidence_sha256:{line_number}")
    if str(row.get("license_status") or "").strip().casefold() not in {"licensed_or_authorized", "license_verified_external"}:
        errors.append(f"license_status_not_verified:{line_number}")
    if str(row.get("source_freshness") or "").strip().casefold() not in _FRESHNESS:
        errors.append(f"source_freshness_not_current:{line_number}")
    return errors


def run_attorney_retrieval_eval(
    dataset_path: Path,
    *,
    search: Callable[[str, int], list[str]],
    min_attorney_rows: int = 1,
    top_k: int = 20,
    strict_provenance: bool = False,
) -> AttorneyRetrievalEvalReport:
    path = dataset_path.resolve()
    if not path.exists() or path.is_symlink() or path.suffix.lower() != ".jsonl":
        raise AttorneyRetrievalEvalError("Attorney retrieval dataset was not found or is not an ordinary JSONL file.")
    rows_seen = 0
    attorney_rows = 0
    metric_rows: list[dict[str, float]] = []
    failures: list[dict[str, Any]] = []
    blockers: list[str] = []
    issue_counts: dict[str, int] = {}
    freshness_counts: dict[str, int] = {}
    provenance_rows = 0
    exact_citation_rows = 0
    exact_citation_hits = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if rows_seen >= MAX_EVAL_ROWS:
                break
            if not line.strip():
                continue
            rows_seen += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                blockers.append(f"invalid_json:{line_number}")
                continue
            if not isinstance(row, dict):
                blockers.append(f"invalid_row:{line_number}")
                continue
            review_status = str(row.get("review_status") or "").casefold()
            method = str(row.get("annotator_or_generation_method") or row.get("generation_method") or "").casefold()
            if "attorney" not in review_status or "not_attorney" in review_status:
                continue
            if "seed" in review_status or "seed" in method or "synthetic" in method or row.get("private_data_allowed_for_training") is True:
                continue
            query = str(row.get("query") or row.get("question") or "").replace("\x00", "").strip()[:MAX_QUERY_CHARS]
            relevant = _relevant_ids(row)
            if not query or not relevant:
                blockers.append(f"missing_query_or_relevant_ids:{line_number}")
                continue
            strict_errors = _strict_provenance_errors(row, line_number=line_number) if strict_provenance else []
            blockers.extend(strict_errors)
            attorney_rows += 1
            labels = _labels(row)
            for label in labels:
                issue_counts[label] = issue_counts.get(label, 0) + 1
            freshness = str(row.get("source_freshness") or "unknown").strip().casefold()
            freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1
            if not strict_errors:
                provenance_rows += 1
            retrieved = search(query, top_k)
            metrics = summarize_ranked_retrieval(retrieved, relevant, ks=(5, 10, 20))
            metric_rows.append(metrics)
            if str(row.get("query_kind") or "").strip().casefold() == "exact_citation":
                exact_citation_rows += 1
                if metrics["recall_at_20"] >= 1.0:
                    exact_citation_hits += 1
            if metrics["recall_at_20"] < 1.0:
                failures.append({
                    "line_number": line_number,
                    "query": query,
                    "expected_source_ids": sorted(relevant),
                    "retrieved_source_ids": retrieved,
                    "reason": "retrieval_miss",
                })
    if attorney_rows < max(1, int(min_attorney_rows)):
        blockers.append("attorney_reviewed_minimum_not_met")
    if strict_provenance and not issue_counts:
        blockers.append("issue_balanced_attorney_dataset_missing")
    keys = ("recall_at_5", "recall_at_10", "recall_at_20", "precision_at_5", "precision_at_10", "precision_at_20", "ndcg_at_5", "ndcg_at_10", "ndcg_at_20", "mrr")
    metrics = {
        key: round(sum(float(row.get(key, 0.0)) for row in metric_rows) / len(metric_rows), 3) if metric_rows else 0.0
        for key in keys
    }
    status = "pass" if not blockers else "blocked"
    return AttorneyRetrievalEvalReport(
        status=status,
        dataset_sha256=_sha_file(path),
        rows_seen=rows_seen,
        attorney_reviewed_rows=attorney_rows,
        evaluated_rows=len(metric_rows),
        metrics=metrics,
        failures=tuple(failures[:500]),
        blockers=tuple(sorted(set(blockers))),
        issue_counts=dict(sorted(issue_counts.items())),
        freshness_counts=dict(sorted(freshness_counts.items())),
        provenance_rows=provenance_rows,
        exact_citation_rows=exact_citation_rows,
        exact_citation_accuracy=(round(exact_citation_hits / exact_citation_rows, 3) if exact_citation_rows else None),
    )
