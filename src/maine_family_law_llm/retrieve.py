"""Dependency-free, citation-aware retrieval with explicit failure diagnostics.

The local fixture retriever is intentionally conservative. It ranks official
sources first, recognizes exact Maine citation/form queries, suppresses duplicate
chunks, and reports why a search was weak or unsuccessful. It does not claim
semantic entailment or current-law verification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from .cite import render_citation_item


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
_CITATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "maine_statute",
        re.compile(
            r"\b(?:title\s+)?\d+(?:-[A-Za-z])?\s*(?:M\.?R\.?S\.?A?\.?)?\s*§+\s*[0-9A-Za-z.-]+\b",
            re.I,
        ),
    ),
    ("maine_opinion", re.compile(r"\b(?:19|20)\d{2}\s+ME\s+\d+\b", re.I)),
    ("maine_form", re.compile(r"\bFM-\d{1,4}[A-Z]?\b", re.I)),
    (
        "maine_rule",
        re.compile(
            r"\b(?:M\.?R\.?\s*)?(?:Civ\.?|App\.?|Evid\.?)\s*P\.?\s*\d+[A-Za-z]?(?:\([a-z0-9]+\))*\b",
            re.I,
        ),
    ),
)
_GENERIC_QUERY_TERMS = {
    "maine", "family", "law", "court", "legal", "question", "help", "please",
    "what", "when", "where", "which", "about", "with", "from", "that", "this",
}


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    source_id: str
    score: float
    title: str
    citation: str
    snippet: str
    metadata: dict[str, Any]
    matched_terms: tuple[str, ...] = ()
    lexical_coverage: float = 0.0
    exact_reference_match: bool = False
    source_class: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    results: tuple[SearchResult, ...]
    failure_class: str = "none"
    recovery_hint: str = ""
    confidence: str = "none"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.failure_class == "none"


class KeywordRetriever:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def search(self, query: str, *, limit: int = 5) -> RetrievalResponse:
        query_text = str(query or "").strip()
        query_tokens = _tokens(query_text)
        if not query_tokens:
            raise ValueError("empty_query_rejected")
        safe_limit = min(20, max(1, int(limit or 5)))
        references = _extract_references(query_text)
        scored: list[tuple[float, int, SearchResult]] = []
        duplicate_candidates = 0

        for order, chunk in enumerate(self.chunks):
            title = str(chunk.get("title", ""))
            citation_hint = str(chunk.get("citation_hint", ""))
            body = str(chunk.get("text", ""))
            text = f"{title} {citation_hint} {body}"
            chunk_tokens = _tokens(text)
            matched_terms = query_tokens.intersection(chunk_tokens)
            overlap = len(matched_terms)
            exact_reference_match = _reference_match(references, text)
            if overlap <= 0 and not exact_reference_match:
                continue

            official = bool(chunk.get("official"))
            source_priority = int(chunk.get("source_priority", 100) or 100)
            source_class = str(
                chunk.get("source_type")
                or chunk.get("source_class")
                or chunk.get("document_type")
                or "unknown"
            )
            coverage = len(matched_terms) / max(len(query_tokens), 1)
            phrase_bonus = 4.0 if _normalized_phrase(query_text) in _normalized_phrase(text) else 0.0
            exact_bonus = 300.0 if exact_reference_match else 0.0
            official_bonus = 100.0 if official else 0.0
            diversity_hint = 1.0 if source_class != "unknown" else 0.0
            score = (
                exact_bonus
                + official_bonus
                + float(overlap)
                + (coverage * 10.0)
                + phrase_bonus
                + diversity_hint
                - (source_priority / 1000.0)
            )
            result = SearchResult(
                chunk_id=str(chunk.get("chunk_id", "")),
                source_id=str(chunk.get("source_id", "")),
                score=round(score, 4),
                title=title,
                citation=render_citation_item(_DictView(chunk)),
                snippet=_snippet(body, matched_terms or query_tokens),
                metadata=dict(chunk),
                matched_terms=tuple(sorted(matched_terms)),
                lexical_coverage=round(coverage, 4),
                exact_reference_match=exact_reference_match,
                source_class=source_class,
            )
            scored.append((score, -order, result))

        if not scored:
            failure_class = "exact_reference_not_found" if references else "no_sources_found"
            recovery_hint = (
                "The exact citation, form ID, or rule reference was not found in the local indexed source bundle. Verify the reference against the live official source."
                if references
                else "No local indexed source chunk matched the query. Add a specific issue, form ID, statute section, or court-paper term."
            )
            return RetrievalResponse(
                query=query_text,
                results=(),
                failure_class=failure_class,
                recovery_hint=recovery_hint,
                confidence="none",
                diagnostics=_diagnostics(
                    query_tokens=query_tokens,
                    references=references,
                    results=(),
                    duplicate_candidates=0,
                    source_chunk_count=len(self.chunks),
                ),
            )

        scored.sort(reverse=True)
        selected: list[SearchResult] = []
        seen_chunks: set[str] = set()
        seen_source_snippets: set[tuple[str, str]] = set()
        for _, _, result in scored:
            chunk_key = result.chunk_id or f"{result.source_id}:{result.snippet[:80]}"
            source_snippet_key = (result.source_id, _normalized_phrase(result.snippet)[:160])
            if chunk_key in seen_chunks or source_snippet_key in seen_source_snippets:
                duplicate_candidates += 1
                continue
            seen_chunks.add(chunk_key)
            seen_source_snippets.add(source_snippet_key)
            selected.append(result)
            if len(selected) >= safe_limit:
                break

        confidence = _confidence(selected, references)
        diagnostics = _diagnostics(
            query_tokens=query_tokens,
            references=references,
            results=tuple(selected),
            duplicate_candidates=duplicate_candidates,
            source_chunk_count=len(self.chunks),
        )
        diagnostics["confidence"] = confidence
        diagnostics["review_warning"] = (
            "Low lexical retrieval confidence. Do not rely on this result without refining the query or checking the live official source."
            if confidence == "low"
            else "Retrieval rank is a source-discovery aid, not a legal correctness or currentness determination."
        )
        return RetrievalResponse(
            query=query_text,
            results=tuple(selected),
            confidence=confidence,
            diagnostics=diagnostics,
        )


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text) if len(token) > 2}


def _normalized_phrase(text: str) -> str:
    return " ".join(TOKEN_RE.findall(str(text or "").lower()))


def _extract_references(text: str) -> tuple[dict[str, str], ...]:
    references: list[dict[str, str]] = []
    for kind, pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(text):
            display = match.group(0).strip()
            references.append(
                {
                    "kind": kind,
                    "display": display,
                    "normalized": _normalized_phrase(display),
                }
            )
    return tuple(references)


def _reference_match(references: tuple[dict[str, str], ...], text: str) -> bool:
    if not references:
        return False
    normalized_text = _normalized_phrase(text)
    return any(reference["normalized"] in normalized_text for reference in references)


def _confidence(results: list[SearchResult], references: tuple[dict[str, str], ...]) -> str:
    if not results:
        return "none"
    top = results[0]
    if top.exact_reference_match:
        return "high"
    substantive_terms = {
        term for term in top.matched_terms if term not in _GENERIC_QUERY_TERMS
    }
    if top.lexical_coverage >= 0.6 and len(substantive_terms) >= 2:
        return "high"
    if top.lexical_coverage >= 0.3 and substantive_terms:
        return "medium"
    if references and any(result.exact_reference_match for result in results):
        return "high"
    return "low"


def _diagnostics(
    *,
    query_tokens: set[str],
    references: tuple[dict[str, str], ...],
    results: tuple[SearchResult, ...],
    duplicate_candidates: int,
    source_chunk_count: int,
) -> dict[str, Any]:
    source_ids = {result.source_id for result in results if result.source_id}
    source_classes = sorted({result.source_class for result in results})
    official_count = sum(1 for result in results if bool(result.metadata.get("official")))
    top_coverage = max((result.lexical_coverage for result in results), default=0.0)
    matched_terms = sorted({term for result in results for term in result.matched_terms})
    return {
        "schema_version": "retrieval_diagnostics_v2",
        "query_token_count": len(query_tokens),
        "substantive_query_terms": sorted(term for term in query_tokens if term not in _GENERIC_QUERY_TERMS),
        "recognized_references": [dict(reference) for reference in references],
        "exact_reference_query": bool(references),
        "source_chunk_count_searched": source_chunk_count,
        "returned_result_count": len(results),
        "distinct_source_count": len(source_ids),
        "official_result_count": official_count,
        "returned_source_classes": source_classes,
        "matched_query_terms": matched_terms,
        "top_lexical_coverage": round(top_coverage, 4),
        "duplicate_candidates_suppressed": duplicate_candidates,
        "current_law_verified": False,
        "human_review_required": True,
    }


def _snippet(text: str, query_tokens: set[str], *, limit: int = 260) -> str:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    snippet = normalized[start : start + limit].strip()
    return snippet + ("..." if start + limit < len(normalized) else "")


class _DictView:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.metadata = payload

    def __getattr__(self, name: str) -> Any:
        try:
            return self.metadata[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
