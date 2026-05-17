from __future__ import annotations

import math
from collections import Counter

from legal.retrieval.query_expansion import tokenize


class DeterministicEmbeddingAdapter:
    """Dependency-free sparse embedding adapter for deterministic local retrieval tests.

    This is not a neural legal embedding model. It creates normalized token-frequency vectors so
    the retrieval pipeline can be measured and swapped for a real embedding backend later without
    changing the app contract.
    """

    model_name = "deterministic_sparse_token_embedding_v1"
    privacy_status = "local_no_external_calls"

    def embed(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        norm = math.sqrt(sum(value * value for value in counts.values()))
        if norm == 0:
            return {}
        return {token: value / norm for token, value in counts.items()}

    def cosine(self, left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
        return sum(value * larger.get(token, 0.0) for token, value in smaller.items())
