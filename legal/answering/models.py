"""Data contracts for citation-first legal answer generation."""

from __future__ import annotations

from dataclasses import dataclass, field


INSUFFICIENT_SOURCE_RESPONSE = (
    "I do not have enough cited Maine family-law source material to answer that. "
    "Add official source material to the corpus and try again."
)



REFUSAL_REASON_INSUFFICIENT_SOURCE_MATERIAL = "insufficient_source_material"
REFUSAL_REASON_NO_RELEVANT_SOURCES = "no_relevant_sources"
REFUSAL_REASON_GENERATOR_FAILED_WITH_RETRIEVAL_FALLBACK = "generator_failed_with_retrieval_fallback"
REFUSAL_REASON_UNSAFE_OR_UNSUPPORTED_QUESTION = "unsafe_or_unsupported_question"
@dataclass(frozen=True)
class SourceSnippet:
    """A retrieved source passage that can support an answer.

    The text should come from an identifiable source. The pipeline treats these
    snippets as the only allowed grounding material for generated answers.
    """

    source_id: str
    title: str
    text: str
    path: str | None = None
    locator: str | None = None

    def citation_label(self) -> str:
        parts = [self.title.strip() or self.source_id]
        if self.locator:
            parts.append(self.locator)
        return " - ".join(parts)
    def text_preview(self, limit: int = 160) -> str:
        raw = (self.text or "").strip()
        if not raw:
            return ""
        normalized = " ".join(raw.split())
        if len(normalized) <= limit:
            return normalized
        if limit <= 3:
            return normalized[:limit]
        return normalized[: max(0, limit - 3)].rstrip() + "..."

    def to_dict(self) -> dict[str, str | None]:
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
    """Retrieved snippets for a single question."""

    question: str
    snippets: tuple[SourceSnippet, ...] = field(default_factory=tuple)

    @property
    def has_sources(self) -> bool:
        return bool(self.snippets)

    @property
    def has_snippets(self) -> bool:
        return bool(self.snippets)


    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "snippets": [snippet.to_dict() for snippet in self.snippets],
            "has_sources": self.has_sources,
        }
@dataclass(frozen=True)
class AnswerRequest:
    """Input to the answer pipeline."""

    question: str
    jurisdiction: str = "Maine"
    matter_type: str | None = None
    max_sources: int = 5


@dataclass(frozen=True)
class AnswerResult:
    """Output from the answer pipeline."""

    answer: str
    citations: tuple[SourceSnippet, ...]
    grounded: bool
    used_model: str | None = None
    warning: str | None = None

    refusal_reason: str | None = None
    remediation_hint: str | None = None
    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "grounded": self.grounded,
            "source_count": len(self.citations),
            "has_source_citations": bool(self.citations),
            "used_model": self.used_model,
            "warning": self.warning,
            "refusal_reason": self.refusal_reason,
            "remediation_hint": self.remediation_hint,
            "citations": [citation.to_dict() for citation in self.citations],
        }
