"""Data contracts for citation-first legal answer generation."""

from __future__ import annotations

from dataclasses import dataclass, field


INSUFFICIENT_SOURCE_RESPONSE = (
    "I do not have enough cited Maine family-law source material to answer that. "
    "Add official source material to the corpus and try again."
)


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


@dataclass(frozen=True)
class RetrievedContext:
    """Retrieved snippets for a single question."""

    question: str
    snippets: tuple[SourceSnippet, ...] = field(default_factory=tuple)

    @property
    def has_sources(self) -> bool:
        return bool(self.snippets)


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
