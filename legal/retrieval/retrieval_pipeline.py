from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from legal.retrieval.hybrid_search import HybridSearch
from legal.retrieval.models import RetrievalResult, SearchDocumentInput, coerce_many
from legal.verifiers.citation_parser import extract_citations
from legal.verifiers.citation_resolver import SourceAuthorityIndex


class RetrievalPipeline:
    """Production-shaped retrieval pipeline for source-grounded Maine legal answers."""

    def __init__(
        self,
        documents: Sequence[SearchDocumentInput] | None = None,
        *,
        hybrid_search: HybridSearch | None = None,
        authority_index: SourceAuthorityIndex | None = None,
    ) -> None:
        self.documents = coerce_many(tuple(documents or ()))
        self.hybrid_search = hybrid_search or HybridSearch()
        self.authority_index = authority_index

    def add_documents(self, documents: Sequence[SearchDocumentInput]) -> None:
        self.documents.extend(coerce_many(tuple(documents)))

    def _citation_resolution_context(self, query: str) -> list[dict[str, Any]]:
        if self.authority_index is None:
            return [citation.to_dict() for citation in extract_citations(query)]
        return [resolution.to_dict() for resolution in self.authority_index.resolve_text(query)]

    def retrieve(
        self,
        query: str,
        documents: Sequence[SearchDocumentInput] | None = None,
        *,
        top_k: int = 10,
        include_text: bool = True,
    ) -> dict[str, Any]:
        search_documents = coerce_many(tuple(documents)) if documents is not None else self.documents
        results: list[RetrievalResult] = self.hybrid_search.search(query, search_documents, top_k=top_k)
        return {
            "query": query,
            "retrieved_sources": [result.to_dict(include_text=include_text) for result in results],
            "source_cards": [result.document.source_card().__dict__ for result in results],
            "citation_resolution_context": self._citation_resolution_context(query),
            "metrics_available": ["recall_at_k", "mrr", "ndcg", "precision_at_k"],
            "retrieval_stack": {
                "lexical": "bm25_exact_citation_lookup",
                "semantic": "deterministic_sparse_embedding_adapter",
                "fusion": "weighted_reciprocal_rank_fusion",
                "authority_weighting": True,
                "freshness_weighting": True,
                "issue_posture_weighting": True,
                "parent_child_chunk_aware": True,
            },
            "review_required": True,
        }
