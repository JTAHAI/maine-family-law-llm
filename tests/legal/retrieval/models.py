from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from legal.documents.models import LegalChunk, SourceCard


@dataclass(frozen=True)
class RetrievalDocument:
    """Searchable legal source or source chunk.

    The retrieval layer searches these normalized records instead of arbitrary strings so every
    result can carry source-card metadata, authority status, freshness, parent document links,
    and issue/procedural labels.
    """

    source_id: str
    text: str
    title: str = ""
    document_id: str | None = None
    chunk_id: str | None = None
    parent_document_id: str | None = None
    source_class: str = "unknown"
    jurisdiction: str = "maine"
    authority_status: str = "stale_unknown"
    freshness_status: str = "unknown"
    citation: str | None = None
    url_or_path: str | None = None
    issue_labels: tuple[str, ...] = ()
    procedural_postures: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_chunk(
        cls,
        chunk: LegalChunk,
        *,
        title: str = "",
        source_class: str = "unknown",
        jurisdiction: str = "maine",
        authority_status: str = "verified_official_maine",
        freshness_status: str = "unknown",
        issue_labels: tuple[str, ...] = (),
        procedural_postures: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> "RetrievalDocument":
        return cls(
            source_id=chunk.source_location.source_id,
            document_id=chunk.parent_document_id,
            chunk_id=chunk.chunk_id,
            parent_document_id=chunk.parent_document_id,
            title=title,
            text=chunk.text,
            source_class=source_class,
            jurisdiction=jurisdiction,
            authority_status=authority_status,
            freshness_status=freshness_status,
            citation=chunk.citation,
            url_or_path=chunk.source_location.url_or_path,
            issue_labels=issue_labels,
            procedural_postures=procedural_postures,
            metadata=metadata or chunk.metadata,
        )

    @property
    def stable_id(self) -> str:
        return self.chunk_id or self.document_id or self.source_id

    def source_card(self) -> SourceCard:
        return SourceCard(
            source_id=self.source_id,
            title=self.title or self.source_id,
            source_class=self.source_class,
            jurisdiction=self.jurisdiction,
            authority_status=self.authority_status,
            citation=self.citation,
            url_or_path=self.url_or_path,
            freshness_status=self.freshness_status,
            hash=self.metadata.get("hash"),
        )


@dataclass(frozen=True)
class RetrievalResult:
    document: RetrievalDocument
    score: float
    rank: int = 0
    method: str = "unknown"
    matched_terms: tuple[str, ...] = ()
    explanation: str = ""
    component_scores: dict[str, float] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.document.source_id

    @property
    def stable_id(self) -> str:
        return self.document.stable_id

    def with_rank(self, rank: int) -> "RetrievalResult":
        return RetrievalResult(
            document=self.document,
            score=self.score,
            rank=rank,
            method=self.method,
            matched_terms=self.matched_terms,
            explanation=self.explanation,
            component_scores=self.component_scores,
        )

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rank": self.rank,
            "score": round(self.score, 6),
            "method": self.method,
            "source_id": self.document.source_id,
            "document_id": self.document.document_id,
            "chunk_id": self.document.chunk_id,
            "citation": self.document.citation,
            "title": self.document.title,
            "source_card": self.document.source_card().__dict__,
            "matched_terms": list(self.matched_terms),
            "explanation": self.explanation,
            "component_scores": {key: round(value, 6) for key, value in self.component_scores.items()},
        }
        if include_text:
            payload["text"] = self.document.text
        return payload


SearchDocumentInput = RetrievalDocument | dict[str, Any] | str


def coerce_retrieval_document(value: SearchDocumentInput, index: int = 0) -> RetrievalDocument:
    """Accept legacy strings/dicts while normalizing to retrieval records."""

    if isinstance(value, RetrievalDocument):
        return value
    if isinstance(value, str):
        return RetrievalDocument(
            source_id=f"legacy-doc-{index}",
            document_id=f"legacy-doc-{index}",
            title=f"Legacy document {index}",
            text=value,
            authority_status="stale_unknown",
            freshness_status="unknown",
        )
    return RetrievalDocument(
        source_id=str(value.get("source_id") or value.get("id") or f"doc-{index}"),
        document_id=value.get("document_id"),
        chunk_id=value.get("chunk_id"),
        parent_document_id=value.get("parent_document_id"),
        title=str(value.get("title") or value.get("name") or value.get("source_id") or f"doc-{index}"),
        text=str(value.get("text") or value.get("body") or ""),
        source_class=str(value.get("source_class") or "unknown"),
        jurisdiction=str(value.get("jurisdiction") or "maine"),
        authority_status=str(value.get("authority_status") or "stale_unknown"),
        freshness_status=str(value.get("freshness_status") or "unknown"),
        citation=value.get("citation"),
        url_or_path=value.get("url_or_path") or value.get("url"),
        issue_labels=tuple(value.get("issue_labels") or ()),
        procedural_postures=tuple(value.get("procedural_postures") or ()),
        metadata=dict(value.get("metadata") or {}),
    )


def coerce_many(values: list[SearchDocumentInput] | tuple[SearchDocumentInput, ...]) -> list[RetrievalDocument]:
    return [coerce_retrieval_document(value, index) for index, value in enumerate(values)]
