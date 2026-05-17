from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def compute_retrieval_metrics(
    retrieved: int,
    relevant_retrieved: int,
    total_relevant: int,
) -> dict[str, float]:
    """Compute basic retrieval precision and recall."""

    precision = relevant_retrieved / retrieved if retrieved else 0.0
    recall = relevant_retrieved / total_relevant if total_relevant else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return round(len(top_k & relevant_ids) / len(relevant_ids), 3)


def precision_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = list(retrieved_ids[:k])
    if not top_k:
        return 0.0
    return round(len(set(top_k) & relevant_ids) / len(top_k), 3)


def mean_reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: set[str]) -> float:
    if not relevant_ids:
        return 0.0
    for index, source_id in enumerate(retrieved_ids, start=1):
        if source_id in relevant_ids:
            return round(1.0 / index, 3)
    return 0.0


def ndcg_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids or k <= 0:
        return 0.0
    dcg = 0.0
    for index, source_id in enumerate(retrieved_ids[:k], start=1):
        if source_id in relevant_ids:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant_ids), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return round(dcg / ideal, 3) if ideal else 0.0


def summarize_ranked_retrieval(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str],
    ks: Sequence[int] = (5, 10, 20),
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for k in ks:
        summary[f"recall_at_{k}"] = recall_at_k(retrieved_ids, relevant_ids, k)
        summary[f"precision_at_{k}"] = precision_at_k(retrieved_ids, relevant_ids, k)
        summary[f"ndcg_at_{k}"] = ndcg_at_k(retrieved_ids, relevant_ids, k)
    summary["mrr"] = mean_reciprocal_rank(retrieved_ids, relevant_ids)
    return summary
