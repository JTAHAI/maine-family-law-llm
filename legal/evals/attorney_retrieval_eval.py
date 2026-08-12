"""Fail-closed attorney-gold retrieval evaluation for v5.12."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from legal.evals.retrieval_metrics import summarize_ranked_retrieval

MAX_EVAL_ROWS = 5_000
MAX_QUERY_CHARS = 2_000


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


def run_attorney_retrieval_eval(
    dataset_path: Path,
    *,
    search: Callable[[str, int], list[str]],
    min_attorney_rows: int = 1,
    top_k: int = 20,
) -> AttorneyRetrievalEvalReport:
    path = dataset_path.resolve()
    if not path.exists() or path.is_symlink() or path.suffix.lower() != ".jsonl":
        raise AttorneyRetrievalEvalError("Attorney retrieval dataset was not found or is not an ordinary JSONL file.")
    rows_seen = 0
    attorney_rows = 0
    metric_rows: list[dict[str, float]] = []
    failures: list[dict[str, Any]] = []
    blockers: list[str] = []
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
            attorney_rows += 1
            retrieved = search(query, top_k)
            metrics = summarize_ranked_retrieval(retrieved, relevant, ks=(5, 10, 20))
            metric_rows.append(metrics)
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
    )
