from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, TypeAlias

from legal.documents.models import SourceCard


@dataclass(frozen=True)
class RetrievalDocument:
    source_id: str
    document_id: str
    title: str
    text: str
    citation: str | None = None
    source_class: str = "unknown_source"
    jurisdiction: str = "maine"
    authority_status: str = "stale_unknown"
    freshness_status: str = "unknown"
    issue_labels: tuple[str, ...] = ()
    procedural_postures: tuple[str, ...] = ()
    url_or_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stable_id(self) -> str:
        return self.source_id or self.document_id

    def source_card(self) -> SourceCard:
        return SourceCard(
            source_id=self.source_id,
            title=self.title,
            citation=self.citation,
            source_class=self.source_class,
            jurisdiction=self.jurisdiction,
            authority_status=self.authority_status,
            freshness_status=self.freshness_status,
            url_or_path=self.url_or_path,
            document_id=self.document_id,
            review_required=True,
        )

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_text:
            payload.pop("text", None)
        return payload


@dataclass(frozen=True)
class RetrievalResult:
    document: RetrievalDocument
    score: float
    method: str
    rank: int = 0
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
            method=self.method,
            rank=rank,
            matched_terms=self.matched_terms,
            explanation=self.explanation,
            component_scores=dict(self.component_scores),
        )

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        return {
            "source_id": self.document.source_id,
            "document_id": self.document.document_id,
            "rank": self.rank,
            "score": self.score,
            "method": self.method,
            "matched_terms": list(self.matched_terms),
            "explanation": self.explanation,
            "component_scores": dict(self.component_scores),
            "source_card": self.document.source_card().to_dict(),
            "document": self.document.to_dict(include_text=include_text),
        }


SearchDocumentInput: TypeAlias = RetrievalDocument | Mapping[str, Any]


def coerce_document(document: SearchDocumentInput) -> RetrievalDocument:
    if isinstance(document, RetrievalDocument):
        return document
    data = dict(document)
    source_id = str(data.get("source_id") or data.get("id") or data.get("document_id") or "unknown-source")
    document_id = str(data.get("document_id") or source_id)
    issue_labels = data.get("issue_labels") or ()
    procedural_postures = data.get("procedural_postures") or data.get("posture_labels") or ()
    if isinstance(issue_labels, list):
        issue_labels = tuple(str(item) for item in issue_labels)
    if isinstance(procedural_postures, list):
        procedural_postures = tuple(str(item) for item in procedural_postures)
    return RetrievalDocument(
        source_id=source_id,
        document_id=document_id,
        title=str(data.get("title") or document_id),
        text=str(data.get("text") or data.get("text_span") or ""),
        citation=data.get("citation"),
        source_class=str(data.get("source_class") or "unknown_source"),
        jurisdiction=str(data.get("jurisdiction") or "maine"),
        authority_status=str(data.get("authority_status") or "stale_unknown"),
        freshness_status=str(data.get("freshness_status") or data.get("retrieved_freshness_status") or "unknown"),
        issue_labels=tuple(issue_labels),
        procedural_postures=tuple(procedural_postures),
        url_or_path=data.get("url_or_path") or data.get("url") or data.get("path"),
        metadata=dict(data.get("metadata") or {}),
    )


def coerce_many(documents: tuple[SearchDocumentInput, ...] | list[SearchDocumentInput]) -> list[RetrievalDocument]:
    return [coerce_document(document) for document in documents]
