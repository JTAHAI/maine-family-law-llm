from __future__ import annotations

from dataclasses import dataclass

INSUFFICIENT_SOURCE_RESPONSE = (
    "I do not have enough cited Maine family-law source material to answer this safely. "
    "Add official Maine family-law source material, then retry."
)
REFUSAL_REASON_INSUFFICIENT_SOURCE_MATERIAL = "insufficient_source_material"
REFUSAL_REASON_NO_RELEVANT_SOURCES = "no_relevant_sources"
REFUSAL_REASON_GENERATOR_FAILED_WITH_RETRIEVAL_FALLBACK = "generator_failed_with_retrieval_fallback"


@dataclass(frozen=True)
class AnswerRequest:
    question: str
    jurisdiction: str = "maine"
    matter_type: str | None = None
    max_sources: int = 5


@dataclass(frozen=True)
class SourceSnippet:
    source_id: str
    title: str
    text: str
    path: str | None = None
    locator: str | None = None

    def citation_label(self) -> str:
        return " - ".join(part for part in (self.title, self.locator) if part)

    def text_preview(self, *, limit: int = 160) -> str:
        clean = " ".join(self.text.split())
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "path": self.path,
            "locator": self.locator,
            "text_preview": self.text_preview(),
            "citation_label": self.citation_label(),
        }


@dataclass(frozen=True)
class RetrievedContext:
    question: str
    snippets: tuple[SourceSnippet, ...]

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "snippets": [snippet.to_dict() for snippet in self.snippets],
        }


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    citations: tuple[SourceSnippet, ...]
    grounded: bool
    used_model: str | None = None
    warning: str | None = None
    refusal_reason: str | None = None
    remediation_hint: str | None = None

    def to_dict(self) -> dict:
        citations = [snippet.to_dict() for snippet in self.citations]
        return {
            "answer": self.answer,
            "citations": citations,
            "grounded": self.grounded,
            "used_model": self.used_model,
            "warning": self.warning,
            "refusal_reason": self.refusal_reason,
            "remediation_hint": self.remediation_hint,
            "source_count": len(citations),
            "has_source_citations": bool(citations),
        }
