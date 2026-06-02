from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceLocation:
    source_id: str
    url_or_path: str | None = None
    parent_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.source_id:
            errors.append("source_id_required")
        if self.start_offset is not None and self.start_offset < 0:
            errors.append("start_offset_negative")
        if self.end_offset is not None and self.start_offset is not None and self.end_offset < self.start_offset:
            errors.append("end_offset_before_start")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceCard:
    source_id: str
    title: str
    citation: str | None = None
    source_class: str | None = None
    jurisdiction: str = "maine"
    authority_status: str = "stale_unknown"
    freshness_status: str = "unknown"
    url_or_path: str | None = None
    document_id: str | None = None
    hash_value: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalDocument:
    document_id: str
    source_location: SourceLocation
    document_type: str
    title: str
    text: str = ""
    citation: str | None = None
    jurisdiction: str = "maine"
    authority_status: str = "verified_official_maine"
    retrieved_freshness_status: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.source_location.source_id

    @property
    def official_citation(self) -> str | None:
        return self.citation

    @property
    def source_class(self) -> str:
        return self.document_type

    def source_card(self, *, hash_value: str | None = None) -> SourceCard:
        return SourceCard(
            source_id=self.source_location.source_id,
            title=self.title,
            citation=self.citation,
            source_class=self.document_type,
            jurisdiction=self.jurisdiction,
            authority_status=self.authority_status,
            freshness_status=self.retrieved_freshness_status,
            url_or_path=self.source_location.url_or_path,
            document_id=self.document_id,
            hash_value=hash_value,
            start_offset=self.source_location.start_offset,
            end_offset=self.source_location.end_offset,
            review_required=True,
        )

    def validate(self) -> list[str]:
        errors = self.source_location.validate()
        if not self.document_id:
            errors.append("document_id_required")
        if not self.document_type:
            errors.append("document_type_required")
        if not self.title:
            errors.append("title_required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatuteTitle(CanonicalDocument):
    title_number: str | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    section_links: list[dict[str, Any]] = field(default_factory=list)
    data_extracted_at: str | None = None


@dataclass
class StatuteSection(CanonicalDocument):
    title_number: str | None = None
    section_number: str | None = None
    section_heading: str | None = None
    subsections: list[str] = field(default_factory=list)


@dataclass
class CourtForm(CanonicalDocument):
    form_id: str | None = None
    version_date: str | None = None
    stale_form_risk: str | None = None


@dataclass
class CourtRule(CanonicalDocument):
    rule_set: str | None = None
    rule_number: str | None = None
    subdivision: str | None = None


@dataclass(frozen=True)
class OpinionReference:
    opinion_id: str
    title: str
    href: str
    decision_date: str | None = None
    docket_number: str | None = None
    citation: str | None = None
    source_id: str | None = None
    jurisdiction: str = "maine"
    authority_status: str = "verified_maine_law_court"

    @property
    def document_id(self) -> str:
        return self.opinion_id

    def source_card(self, *, hash_value: str | None = None) -> SourceCard:
        return SourceCard(
            source_id=self.source_id or self.opinion_id,
            title=self.title,
            citation=self.citation,
            source_class="law_court_opinion",
            jurisdiction=self.jurisdiction,
            authority_status=self.authority_status,
            freshness_status="unknown",
            url_or_path=self.href,
            document_id=self.opinion_id,
            hash_value=hash_value,
            review_required=True,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.opinion_id:
            errors.append("opinion_id_required")
        if not self.href:
            errors.append("href_required")
        if not self.title:
            errors.append("title_required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegalChunk:
    chunk_id: str
    parent_document_id: str
    source_location: SourceLocation
    text: str
    citation: str | None = None
    jurisdiction: str = "maine"
    source_class: str = "legal_chunk"
    authority_status: str = "stale_unknown"

    @property
    def source_id(self) -> str:
        return self.source_location.source_id

    def validate(self) -> list[str]:
        errors = self.source_location.validate()
        if not self.chunk_id:
            errors.append("chunk_id_required")
        if not self.parent_document_id:
            errors.append("parent_document_id_required")
        if not self.text:
            errors.append("text_required")
        return errors

    def source_card(self, *, hash_value: str | None = None) -> SourceCard:
        return SourceCard(
            source_id=self.source_location.source_id,
            title=self.parent_document_id,
            citation=self.citation,
            source_class=self.source_class,
            jurisdiction=self.jurisdiction,
            authority_status=self.authority_status,
            freshness_status="unknown",
            url_or_path=self.source_location.url_or_path,
            document_id=self.parent_document_id,
            hash_value=hash_value,
            start_offset=self.source_location.start_offset,
            end_offset=self.source_location.end_offset,
            review_required=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
