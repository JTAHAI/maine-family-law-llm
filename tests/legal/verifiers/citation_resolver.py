from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal.verifiers.citation_parser import ParsedCitation, extract_citations


@dataclass(frozen=True)
class CitationResolution:
    citation: ParsedCitation
    status: str
    source_id: str | None = None
    authority_status: str = "not_found"
    message: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation.to_dict(),
            "status": self.status,
            "source_id": self.source_id,
            "authority_status": self.authority_status,
            "message": self.message,
            "metadata": self.metadata or {},
        }


class SourceAuthorityIndex:
    """Deterministic citation-to-source lookup table.

    The index is intentionally separate from the generator. It only resolves citations
    to known source IDs already admitted through ingestion and canonical parsing.
    """

    def __init__(self) -> None:
        self._by_kind_and_citation: dict[tuple[str, str], dict[str, Any]] = {}

    def add(
        self,
        *,
        kind: str,
        normalized_citation: str,
        source_id: str,
        authority_status: str = "verified_official_maine",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._by_kind_and_citation[(kind, normalized_citation)] = {
            "source_id": source_id,
            "authority_status": authority_status,
            "metadata": metadata or {},
        }

    def add_statute(self, title: str, section: str, source_id: str) -> None:
        from legal.verifiers.citation_parser import normalize_maine_statute

        self.add(
            kind="maine_statute",
            normalized_citation=normalize_maine_statute(title, section),
            source_id=source_id,
            authority_status="verified_official_maine",
            metadata={"title": title, "section": section},
        )

    def add_case(self, year: str, number: str, source_id: str) -> None:
        from legal.verifiers.citation_parser import normalize_maine_case

        self.add(
            kind="maine_case",
            normalized_citation=normalize_maine_case(year, number),
            source_id=source_id,
            authority_status="verified_maine_law_court",
            metadata={"year": year, "number": number},
        )

    def add_rule(self, normalized_rule: str, source_id: str) -> None:
        self.add(
            kind="maine_rule",
            normalized_citation=normalized_rule,
            source_id=source_id,
            authority_status="verified_official_maine",
        )

    def add_form(self, form_id: str, source_id: str) -> None:
        self.add(
            kind="maine_form",
            normalized_citation=form_id,
            source_id=source_id,
            authority_status="verified_official_maine",
        )

    def add_federal(self, normalized_citation: str, source_id: str) -> None:
        self.add(
            kind="federal_statute",
            normalized_citation=normalized_citation,
            source_id=source_id,
            authority_status="verified_federal",
        )

    def to_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for (kind, normalized), value in sorted(self._by_kind_and_citation.items()):
            rows.append(
                {
                    "kind": kind,
                    "normalized_citation": normalized,
                    "source_id": value["source_id"],
                    "authority_status": value["authority_status"],
                    "metadata": value["metadata"],
                }
            )
        return rows

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]]) -> "SourceAuthorityIndex":
        index = cls()
        for row in rows:
            index.add(
                kind=str(row["kind"]),
                normalized_citation=str(row["normalized_citation"]),
                source_id=str(row["source_id"]),
                authority_status=str(row.get("authority_status") or "stale_unknown"),
                metadata=dict(row.get("metadata") or {}),
            )
        return index

    def resolve(self, citation: ParsedCitation) -> CitationResolution:
        found = self._by_kind_and_citation.get((citation.kind, citation.normalized))
        if not found:
            return CitationResolution(
                citation=citation,
                status="not_found",
                message="citation did not resolve to an admitted source ID",
            )
        return CitationResolution(
            citation=citation,
            status="found",
            source_id=found["source_id"],
            authority_status=found["authority_status"],
            message="citation resolved to admitted source ID",
            metadata=found["metadata"],
        )

    def resolve_text(self, text: str) -> list[CitationResolution]:
        return [self.resolve(citation) for citation in extract_citations(text)]
