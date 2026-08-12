from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal.verifiers.citation_parser import ParsedCitation, extract_citations


_AUTHORITY_PRIORITY = {
    "verified_official_maine": 0,
    "verified_maine_law_court": 1,
    "verified_federal": 2,
    "verified_public_api": 3,
    "user_provided_only": 8,
    "stale_unknown": 9,
    "not_found": 99,
}
_FRESHNESS_PRIORITY = {
    "current": 0,
    "fresh": 1,
    "known": 2,
    "retrieved_timestamp_known": 3,
    "unknown": 8,
    "stale": 9,
}
_DIRECT_SOURCE_CLASS_BONUS = {
    "statute_section": 0,
    "court_form": 0,
    "law_court_opinion": 0,
    "court_rule": 0,
    "statute_title_index": 5,
    "court_forms_index": 5,
    "law_court_opinion_index": 5,
    "court_rules_index": 5,
}


@dataclass(frozen=True)
class CitationResolution:
    citation: ParsedCitation
    status: str
    source_id: str | None = None
    authority_status: str = "not_found"
    message: str = ""
    metadata: dict[str, Any] | None = None
    candidates: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation.to_dict(),
            "status": self.status,
            "source_id": self.source_id,
            "authority_status": self.authority_status,
            "message": self.message,
            "metadata": self.metadata or {},
            "candidates": [dict(candidate) for candidate in self.candidates],
        }


class SourceAuthorityIndex:
    """Deterministic citation-to-source lookup with ranked multi-candidate support.

    More than one parsed record can legitimately carry the same citation, such as
    an index reference plus the direct section or an official form plus an index
    entry.  The index retains all admitted candidates and deterministically chooses
    the strongest direct/current authority as the primary resolution.
    """

    def __init__(self) -> None:
        self._by_kind_and_citation: dict[tuple[str, str], list[dict[str, Any]]] = {}

    @staticmethod
    def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        authority = _AUTHORITY_PRIORITY.get(str(candidate.get("authority_status") or "stale_unknown"), 50)
        freshness = _FRESHNESS_PRIORITY.get(str(metadata.get("freshness_status") or "unknown").lower(), 6)
        source_class = _DIRECT_SOURCE_CLASS_BONUS.get(str(metadata.get("source_class") or ""), 3)
        return authority, freshness, source_class, str(candidate.get("source_id") or "")

    def add(
        self,
        *,
        kind: str,
        normalized_citation: str,
        source_id: str,
        authority_status: str = "verified_official_maine",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = (kind, normalized_citation)
        candidates = self._by_kind_and_citation.setdefault(key, [])
        payload = {
            "source_id": source_id,
            "authority_status": authority_status,
            "metadata": metadata or {},
        }
        for index, existing in enumerate(candidates):
            if existing["source_id"] == source_id:
                candidates[index] = payload
                break
        else:
            candidates.append(payload)
        candidates.sort(key=self._candidate_sort_key)

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
        for (kind, normalized), candidates in sorted(self._by_kind_and_citation.items()):
            for rank, value in enumerate(candidates, start=1):
                rows.append(
                    {
                        "kind": kind,
                        "normalized_citation": normalized,
                        "source_id": value["source_id"],
                        "authority_status": value["authority_status"],
                        "metadata": value["metadata"],
                        "candidate_rank": rank,
                        "candidate_count": len(candidates),
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

    def candidates_for(self, citation: ParsedCitation) -> tuple[dict[str, Any], ...]:
        candidates = self._by_kind_and_citation.get((citation.kind, citation.normalized), [])
        return tuple(
            {
                "source_id": item["source_id"],
                "authority_status": item["authority_status"],
                "metadata": dict(item.get("metadata") or {}),
                "rank": rank,
            }
            for rank, item in enumerate(candidates, start=1)
        )

    def resolve(self, citation: ParsedCitation) -> CitationResolution:
        candidates = self.candidates_for(citation)
        if not candidates:
            return CitationResolution(
                citation=citation,
                status="not_found",
                message="citation did not resolve to an admitted source ID",
            )
        primary = candidates[0]
        metadata = dict(primary.get("metadata") or {})
        metadata["candidate_count"] = len(candidates)
        metadata["alternate_source_ids"] = [candidate["source_id"] for candidate in candidates[1:]]
        return CitationResolution(
            citation=citation,
            status="found",
            source_id=str(primary["source_id"]),
            authority_status=str(primary["authority_status"]),
            message=(
                "citation resolved to admitted source ID"
                if len(candidates) == 1
                else f"citation resolved to {len(candidates)} admitted sources; strongest candidate selected"
            ),
            metadata=metadata,
            candidates=candidates,
        )

    def resolve_text(self, text: str) -> list[CitationResolution]:
        return [self.resolve(citation) for citation in extract_citations(text)]
