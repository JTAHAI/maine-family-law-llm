"""Dependency-free keyword retrieval over citation-aware chunks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .cite import render_citation_item


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    source_id: str
    score: float
    title: str
    citation: str
    snippet: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    results: tuple[SearchResult, ...]
    failure_class: str = "none"
    recovery_hint: str = ""

    @property
    def ok(self) -> bool:
        return self.failure_class == "none"


class KeywordRetriever:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def search(self, query: str, *, limit: int = 5) -> RetrievalResponse:
        query_tokens = _tokens(query)
        if not query_tokens:
            raise ValueError("empty_query_rejected")
        scored: list[tuple[float, int, SearchResult]] = []
        for order, chunk in enumerate(self.chunks):
            text = f"{chunk.get('title', '')} {chunk.get('citation_hint', '')} {chunk.get('text', '')}"
            overlap = len(query_tokens.intersection(_tokens(text)))
            if overlap <= 0:
                continue
            official = bool(chunk.get("official"))
            source_priority = int(chunk.get("source_priority", 100) or 100)
            score = float(overlap) + (100.0 if official else 0.0) - (source_priority / 1000.0)
            snippet = _snippet(str(chunk.get("text", "")), query_tokens)
            result = SearchResult(
                chunk_id=str(chunk.get("chunk_id", "")),
                source_id=str(chunk.get("source_id", "")),
                score=round(score, 4),
                title=str(chunk.get("title", "")),
                citation=render_citation_item(_DictView(chunk)),
                snippet=snippet,
                metadata=dict(chunk),
            )
            scored.append((score, -order, result))
        if not scored:
            return RetrievalResponse(
                query=query,
                results=(),
                failure_class="no_sources_found",
                recovery_hint="No local indexed source chunk matched the query.",
            )
        scored.sort(reverse=True)
        return RetrievalResponse(query=query, results=tuple(item[2] for item in scored[:limit]))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text) if len(token) > 2}


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
