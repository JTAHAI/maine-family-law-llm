from __future__ import annotations

from collections.abc import Sequence

from legal.retrieval.embedding_adapter import DeterministicEmbeddingAdapter
from legal.retrieval.models import RetrievalResult, SearchDocumentInput, coerce_many
from legal.retrieval.query_expansion import expand_query


class DeterministicSemanticSearch:
    """Local semantic-ish search using the embedding adapter contract.

    It expands Maine family-law vocabulary before computing sparse-vector cosine similarity.
    The adapter can be replaced later with a real legal embedding model.
    """

    def __init__(self, adapter: DeterministicEmbeddingAdapter | None = None) -> None:
        self.adapter = adapter or DeterministicEmbeddingAdapter()

    def search(
        self,
        query: str,
        documents: Sequence[SearchDocumentInput],
        *,
        top_k: int = 20,
    ) -> list[RetrievalResult]:
        normalized_documents = coerce_many(tuple(documents))
        expanded_query = " ".join(expand_query(query)) or query
        query_vector = self.adapter.embed(expanded_query)
        results: list[RetrievalResult] = []
        for document in normalized_documents:
            document_vector = self.adapter.embed(
                " ".join(part for part in (document.title, document.citation or "", document.text) if part)
            )
            score = self.adapter.cosine(query_vector, document_vector)
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    document=document,
                    score=score,
                    method="deterministic_semantic",
                    explanation="Sparse cosine similarity over expanded Maine family-law terms",
                    component_scores={"semantic": score},
                )
            )
        ranked = sorted(results, key=lambda result: (-result.score, result.document.source_id))[:top_k]
        return [result.with_rank(index + 1) for index, result in enumerate(ranked)]
