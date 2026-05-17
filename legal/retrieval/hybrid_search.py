from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from legal.retrieval.authority_ranker import AuthorityRanker
from legal.retrieval.lexical_search import BM25LexicalSearch, LexicalSearch
from legal.retrieval.models import RetrievalDocument, RetrievalResult, SearchDocumentInput, coerce_many
from legal.retrieval.query_expansion import expand_query
from legal.retrieval.semantic_search import DeterministicSemanticSearch


AUTHORITY_BOOSTS = {
    "verified_official_maine": 0.30,
    "verified_maine_law_court": 0.25,
    "verified_federal": 0.15,
    "verified_public_api": 0.05,
    "user_provided_only": -0.05,
    "stale_unknown": -0.15,
    "not_found": -0.50,
}
FRESHNESS_BOOSTS = {
    "current": 0.15,
    "fresh": 0.10,
    "known": 0.05,
    "unknown": -0.05,
    "stale": -0.25,
}


@dataclass(frozen=True)
class HybridSearchConfig:
    lexical_weight: float = 1.0
    semantic_weight: float = 0.8
    rrf_k: int = 60
    top_k_per_component: int = 40


class HybridSearch:
    def __init__(
        self,
        *,
        lexical: BM25LexicalSearch | None = None,
        semantic: DeterministicSemanticSearch | None = None,
        authority_ranker: AuthorityRanker | None = None,
        config: HybridSearchConfig | None = None,
    ) -> None:
        self.lexical = lexical or BM25LexicalSearch()
        self.semantic = semantic or DeterministicSemanticSearch()
        self.authority_ranker = authority_ranker or AuthorityRanker()
        self.config = config or HybridSearchConfig()
        # Keep the old scaffold behavior available for callers that explicitly need it.
        self.legacy_substring_search = LexicalSearch()

    def _issue_posture_boost(self, query: str, document: RetrievalDocument) -> float:
        terms = set(expand_query(query))
        label_tokens = set()
        for label in (*document.issue_labels, *document.procedural_postures):
            label_tokens.update(label.lower().replace("_", " ").split())
        if not label_tokens:
            return 0.0
        overlap = terms & label_tokens
        return min(0.12, 0.03 * len(overlap))

    def _authority_boost(self, document: RetrievalDocument) -> float:
        boost = AUTHORITY_BOOSTS.get(document.authority_status, -0.10)
        freshness = FRESHNESS_BOOSTS.get(document.freshness_status, 0.0)
        return boost + freshness

    def _rrf_fuse(
        self,
        component_results: list[tuple[str, float, list[RetrievalResult]]],
        query: str,
    ) -> list[RetrievalResult]:
        by_id: dict[str, RetrievalResult] = {}
        scores: dict[str, float] = {}
        components: dict[str, dict[str, float]] = {}
        methods: dict[str, list[str]] = {}
        matched_terms: dict[str, set[str]] = {}

        for name, weight, results in component_results:
            for result in results:
                stable_id = result.stable_id
                by_id.setdefault(stable_id, result)
                methods.setdefault(stable_id, []).append(result.method)
                matched_terms.setdefault(stable_id, set()).update(result.matched_terms)
                contribution = weight * (1.0 / (self.config.rrf_k + max(result.rank, 1)))
                # RRF is rank-based, so preserve decisive exact citation/form lookup evidence
                # as a bounded bonus. Without this, a current official rule mentioning
                # "family matter" can outrank an exact FM-002 form lookup.
                exact_bonus = min(0.40, float(result.component_scores.get("exact_citation", 0.0)) * 0.10)
                contribution += exact_bonus
                scores[stable_id] = scores.get(stable_id, 0.0) + contribution
                components.setdefault(stable_id, {})[name] = contribution

        fused: list[RetrievalResult] = []
        for stable_id, result in by_id.items():
            authority_boost = self._authority_boost(result.document)
            issue_posture_boost = self._issue_posture_boost(query, result.document)
            authority_penalty = self.authority_ranker.score(result.document.authority_status) * -0.005
            total = scores[stable_id] + authority_boost + issue_posture_boost + authority_penalty
            component_score = dict(components.get(stable_id, {}))
            component_score.update(
                {
                    "authority_freshness": authority_boost,
                    "issue_posture": issue_posture_boost,
                    "authority_rank_tiebreak": authority_penalty,
                }
            )
            fused.append(
                RetrievalResult(
                    document=result.document,
                    score=total,
                    method="hybrid_rrf_authority_weighted",
                    matched_terms=tuple(sorted(matched_terms.get(stable_id, set()))),
                    explanation="Hybrid reciprocal-rank fusion with authority, freshness, issue, and posture weighting",
                    component_scores=component_score,
                )
            )
        ranked = sorted(
            fused,
            key=lambda item: (
                -item.score,
                self.authority_ranker.score(item.document.authority_status),
                item.document.source_id,
            ),
        )
        return [result.with_rank(index + 1) for index, result in enumerate(ranked)]

    def search(
        self,
        query: str,
        documents: Sequence[SearchDocumentInput],
        *,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        normalized_documents = coerce_many(tuple(documents))
        lexical_results = self.lexical.search(
            query, normalized_documents, top_k=self.config.top_k_per_component
        )
        semantic_results = self.semantic.search(
            query, normalized_documents, top_k=self.config.top_k_per_component
        )
        fused = self._rrf_fuse(
            [
                ("lexical", self.config.lexical_weight, lexical_results),
                ("semantic", self.config.semantic_weight, semantic_results),
            ],
            query,
        )
        return fused[:top_k]
