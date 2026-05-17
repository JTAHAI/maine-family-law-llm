from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Sequence

from legal.retrieval.models import RetrievalDocument, RetrievalResult, SearchDocumentInput, coerce_many
from legal.retrieval.query_expansion import expand_query, tokenize
from legal.verifiers.citation_parser import extract_citations


class LexicalSearch:
    """Backward-compatible exact substring search used by early scaffold tests."""

    def search(self, query: str, documents: list[str]):
        query = query.lower()
        return [document for document in documents if query in document.lower()]


class BM25LexicalSearch:
    """Small deterministic BM25 implementation for Maine legal source chunks."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75, expand_queries: bool = True) -> None:
        self.k1 = k1
        self.b = b
        self.expand_queries = expand_queries

    def _idf(self, documents: Sequence[RetrievalDocument]) -> dict[str, float]:
        doc_freq: dict[str, int] = defaultdict(int)
        for document in documents:
            for token in set(tokenize(document.text + " " + document.title + " " + (document.citation or ""))):
                doc_freq[token] += 1
        total = len(documents)
        return {
            token: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for token, count in doc_freq.items()
        }

    def _exact_citation_boost(self, query: str, document: RetrievalDocument) -> float:
        citations = extract_citations(query)
        if not citations:
            return 0.0
        haystack = " ".join(
            part for part in (document.citation, document.title, document.text, document.source_id) if part
        ).lower()
        boost = 0.0
        for citation in citations:
            if citation.normalized.lower() in haystack or citation.raw.lower() in haystack:
                boost += 4.0
            elif citation.kind == "maine_form" and citation.form_id and citation.form_id.lower() in haystack:
                boost += 4.0
            elif citation.section and citation.section.lower() in haystack and citation.title and citation.title.lower() in haystack:
                boost += 2.0
        return boost

    def search(
        self,
        query: str,
        documents: Sequence[SearchDocumentInput],
        *,
        top_k: int = 20,
    ) -> list[RetrievalResult]:
        normalized_documents = coerce_many(tuple(documents))
        if not normalized_documents:
            return []

        query_terms = expand_query(query) if self.expand_queries else tokenize(query)
        if not query_terms and not extract_citations(query):
            return []

        idf = self._idf(normalized_documents)
        avg_len = sum(len(tokenize(document.text)) for document in normalized_documents) / max(
            len(normalized_documents), 1
        )
        results: list[RetrievalResult] = []
        for document in normalized_documents:
            field_text = " ".join(
                part for part in (document.title, document.citation or "", document.text) if part
            )
            doc_tokens = tokenize(field_text)
            token_counts = Counter(doc_tokens)
            doc_len = max(len(doc_tokens), 1)
            score = 0.0
            matched_terms: list[str] = []
            for term in query_terms:
                freq = token_counts.get(term, 0)
                if not freq:
                    continue
                matched_terms.append(term)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / max(avg_len, 1))
                score += idf.get(term, 0.0) * numerator / denominator

            exact_boost = self._exact_citation_boost(query, document)
            score += exact_boost
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    document=document,
                    score=score,
                    method="bm25_exact_citation" if exact_boost else "bm25",
                    matched_terms=tuple(sorted(set(matched_terms))),
                    explanation="BM25 lexical search with exact citation/form boost",
                    component_scores={"bm25": score - exact_boost, "exact_citation": exact_boost},
                )
            )

        ranked = sorted(results, key=lambda result: (-result.score, result.document.source_id))[:top_k]
        return [result.with_rank(index + 1) for index, result in enumerate(ranked)]
