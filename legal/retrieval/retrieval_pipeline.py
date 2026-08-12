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
        citation_context = self._citation_resolution_context(query)
        if self.authority_index is not None and citation_context:
            by_source_id = {document.source_id: document for document in search_documents}
            exact_ids: list[str] = []
            for resolution in citation_context:
                if resolution.get("status") != "found":
                    continue
                candidates = resolution.get("candidates") or []
                for candidate in candidates:
                    source_id = str(candidate.get("source_id") or "")
                    if source_id and source_id not in exact_ids:
                        exact_ids.append(source_id)
                primary = str(resolution.get("source_id") or "")
                if primary and primary not in exact_ids:
                    exact_ids.insert(0, primary)
            exact_results = [
                RetrievalResult(
                    document=by_source_id[source_id],
                    score=1000.0 - rank,
                    method="admitted_exact_citation",
                    matched_terms=("exact_citation",),
                    explanation="Exact citation resolved to an admitted official source",
                    component_scores={"exact_citation": 1000.0 - rank},
                )
                for rank, source_id in enumerate(exact_ids)
                if source_id in by_source_id
            ]
            exact_set = {result.source_id for result in exact_results}
            results = exact_results + [result for result in results if result.source_id not in exact_set]
            results = [result.with_rank(index + 1) for index, result in enumerate(results[:top_k])]
        return {
            "query": query,
            "retrieved_sources": [result.to_dict(include_text=include_text) for result in results],
            "source_cards": [result.document.source_card().__dict__ for result in results],
            "citation_resolution_context": citation_context,
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
