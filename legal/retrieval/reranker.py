from __future__ import annotations

from legal.retrieval.authority_ranker import AuthorityRanker


class MaineAuthorityReranker:
    def __init__(self, ranker: AuthorityRanker | None = None) -> None:
        self.ranker = ranker or AuthorityRanker()

    def rerank(self, results: list[dict]):
        return self.ranker.rank(results)
