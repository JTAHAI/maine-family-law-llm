from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class SourceLocation:
    """Exact source location for a canonical legal object or chunk."""

    source_id: str
    url_or_path: str | None = None
    parent_id: str | None = None
    anchor: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.source_id:
            problems.append("missing source_id")
        if self.start_offset is not None and self.end_offset is not None:
            if self.end_offset < self.start_offset:
                problems.append("end_offset precedes start_offset")
        return problems


@dataclass(frozen=True)
class SourceCard:
    """User-facing source card metadata; not legal correctness by itself."""

    source_id: str
    title: str
    source_class: str
    jurisdiction: str = "maine"
    authority_status: str = "verified_official_maine"
    citation: str | None = None
    url_or_path: str | None = None
    freshness_status: str = "unknown"
    hash: str | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        for name in ("source_id", "title", "source_class", "jurisdiction", "authority_status"):
            if not getattr(self, name):
                problems.append(f"missing {name}")
        return problems


@dataclass(frozen=True)
class LegalChunk:
    chunk_id: str
    parent_document_id: str
    source_location: SourceLocation
    text: str
    citation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        problems = self.source_location.validate()
        if not self.chunk_id:
            problems.append("missing chunk_id")
        if not self.parent_document_id:
            problems.append("missing parent_document_id")
        if not self.text.strip():
            problems.append("empty chunk text")
        return problems


@dataclass(frozen=True)
class CanonicalDocument:
    document_id: str
    source_location: SourceLocation
    document_type: str
    title: str
    text: str = ""
    citation: str | None = None
    effective_date: date | None = None
    retrieved_freshness_status: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        problems = self.source_location.validate()
        for name in ("document_id", "document_type", "title"):
            if not getattr(self, name):
                problems.append(f"missing {name}")
        return problems

    def source_card(self, *, source_class: str | None = None, hash_value: str | None = None) -> SourceCard:
        return SourceCard(
            source_id=self.source_location.source_id,
            title=self.title,
            source_class=source_class or self.document_type,
            citation=self.citation,
            url_or_path=self.source_location.url_or_path,
            freshness_status=self.retrieved_freshness_status,
            hash=hash_value,
        )


@dataclass(frozen=True)
class StatuteSection(CanonicalDocument):
    title_number: str = ""
    section_number: str = ""
    section_heading: str = ""
    subsections: list[str] = field(default_factory=list)

    @property
    def official_citation(self) -> str:
        return f"{self.title_number} M.R.S. § {self.section_number}".strip()


@dataclass(frozen=True)
class StatuteTitle(CanonicalDocument):
    title_number: str = ""
    chapters: list[dict[str, str]] = field(default_factory=list)
    section_links: list[dict[str, str]] = field(default_factory=list)
    data_extracted_at: str | None = None


@dataclass(frozen=True)
class CourtRule(CanonicalDocument):
    rule_set: str = ""
    rule_number: str | None = None


@dataclass(frozen=True)
class CourtForm(CanonicalDocument):
    form_id: str | None = None
    version_date: str | None = None
    required_fields: list[str] = field(default_factory=list)
    stale_form_risk: str = "unknown"


@dataclass(frozen=True)
class OpinionReference:
    opinion_id: str
    title: str
    href: str
    decision_date: str | None = None
    docket_number: str | None = None
    citation: str | None = None
    court: str = "Maine Supreme Judicial Court"
    source_id: str | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.opinion_id:
            problems.append("missing opinion_id")
        if not self.title:
            problems.append("missing title")
        if not self.href:
            problems.append("missing href")
        return problems
