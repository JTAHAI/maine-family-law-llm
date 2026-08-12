from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.retrieval.authority_graph import AuthorityGraph
from legal.verifiers.citation_parser import ParsedCitation, extract_citations
from legal.verifiers.citation_resolver import SourceAuthorityIndex

TEXT_FIELDS_FOR_CITATION_DISCOVERY = (
    "text",
    "title",
    "summary",
    "holding",
    "holdings",
    "instructions",
    "filing_context",
    "disposition",
)


def _statute_pinpoints(record: "ParsedAuthorityRecord") -> list[tuple[str, dict[str, int]]]:
    """Return admitted subsection aliases with exact offsets into parsed text."""
    if record.authority_kind != "statute_section" or not record.citation:
        return []
    text = str(record.row.get("text") or "")
    subsections = record.row.get("subsections")
    if not text or not isinstance(subsections, list):
        return []
    results: list[tuple[str, dict[str, int]]] = []
    for subsection in subsections:
        value = str(subsection).strip()
        match = re.match(r"(?P<number>\d+[A-Z]?)\.\s+", value, re.I)
        if not match:
            continue
        start = text.find(value)
        if start < 0:
            continue
        number = match.group("number").upper()
        results.append(
            (
                f"{record.citation}({number})",
                {"start_offset": start, "end_offset": start + len(value)},
            )
        )
    return results


@dataclass(frozen=True)
class ParsedAuthorityRecord:
    """Canonical view of one parsed authority row.

    Parsed rows intentionally keep both the raw snapshot source ID and the more specific
    parsed record ID.  Citation resolution should resolve to the most specific parsed
    record available, while retaining snapshot lineage in metadata.
    """

    canonical_source_id: str
    snapshot_source_id: str
    source_class: str
    authority_kind: str
    jurisdiction: str
    title: str = ""
    citation: str | None = None
    source_hash: str | None = None
    freshness_status: str = "unknown"
    parser_status: str | None = None
    source_span: dict[str, Any] = field(default_factory=dict)
    row: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ParsedAuthorityRecord":
        canonical_source_id = str(row.get("record_id") or row.get("source_id") or "").strip()
        snapshot_source_id = str(row.get("source_id") or canonical_source_id).strip()
        return cls(
            canonical_source_id=canonical_source_id,
            snapshot_source_id=snapshot_source_id,
            source_class=str(row.get("source_class") or "unknown"),
            authority_kind=str(row.get("authority_kind") or "unknown"),
            jurisdiction=str(row.get("jurisdiction") or "maine"),
            title=str(row.get("title") or ""),
            citation=str(row.get("citation") or "") or None,
            source_hash=row.get("source_hash"),
            freshness_status=str(row.get("freshness_status") or "unknown"),
            parser_status=row.get("parser_status"),
            source_span=dict(row.get("source_span") or {}),
            row=dict(row),
        )

    @property
    def authority_status(self) -> str:
        if self.jurisdiction.lower() == "federal":
            return "verified_federal"
        if "opinion" in self.authority_kind or "law_court" in self.source_class:
            return "verified_maine_law_court"
        if self.jurisdiction.lower() == "maine":
            return "verified_official_maine"
        return "stale_unknown"

    def searchable_text(self) -> str:
        parts = [self.title, self.citation or ""]
        for field_name in TEXT_FIELDS_FOR_CITATION_DISCOVERY:
            value = self.row.get(field_name)
            if isinstance(value, list):
                parts.append(" ".join(str(item) for item in value))
            elif value:
                parts.append(str(value))
        return "\n".join(part for part in parts if part)

    def source_card(self) -> dict[str, Any]:
        return {
            "source_id": self.canonical_source_id,
            "snapshot_source_id": self.snapshot_source_id,
            "title": self.title or self.canonical_source_id,
            "citation": self.citation,
            "source_class": self.source_class,
            "authority_kind": self.authority_kind,
            "jurisdiction": self.jurisdiction,
            "authority_status": self.authority_status,
            "freshness_status": self.freshness_status,
            "hash": self.source_hash,
            "source_span": self.source_span,
            "source_url_or_path": self.row.get("source_url_or_path"),
            "snapshot_path": self.row.get("snapshot_path"),
            "negative_treatment_status": self.row.get(
                "negative_treatment_status", "negative_treatment_unknown"
            )
            if "opinion" in self.authority_kind
            else self.row.get("negative_treatment_status"),
        }


def iter_parsed_authority_rows(data_root: str | Path) -> Iterable[dict[str, Any]]:
    parsed_store = Path(data_root).resolve() / "parsed_authority_store"
    for path in sorted(parsed_store.rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("_parsed_relative_path", str(path.relative_to(parsed_store)))
            row.setdefault("_parsed_line_number", line_number)
            yield row


def load_parsed_authority_records(data_root: str | Path) -> list[ParsedAuthorityRecord]:
    return [ParsedAuthorityRecord.from_row(row) for row in iter_parsed_authority_rows(data_root)]


class ParsedAuthorityIndexBuilder:
    """Build citation index, authority graph, and source-card manifest from parsed authority."""

    def __init__(self, *, data_root: str | Path) -> None:
        self.data_root = Path(data_root).resolve()
        self.authority_layer_dir = self.data_root / "authority_layer"

    def build_source_authority_index(self, records: list[ParsedAuthorityRecord] | None = None) -> SourceAuthorityIndex:
        records = records or load_parsed_authority_records(self.data_root)
        index = SourceAuthorityIndex()
        for record in records:
            if not record.citation:
                continue
            citations = extract_citations(record.citation)
            if not citations and record.row.get("form_id"):
                citations = extract_citations(str(record.row.get("form_id")))
            for citation in citations:
                metadata = {
                    "snapshot_source_id": record.snapshot_source_id,
                    "title": record.title,
                    "source_class": record.source_class,
                    "authority_kind": record.authority_kind,
                    "freshness_status": record.freshness_status,
                    "source_hash": record.source_hash,
                    "source_span": record.source_span,
                }
                index.add(
                    kind=citation.kind,
                    normalized_citation=citation.normalized,
                    source_id=record.canonical_source_id,
                    authority_status=record.authority_status,
                    metadata=metadata,
                )
            for pinpoint, pinpoint_span in _statute_pinpoints(record):
                parsed_pinpoints = extract_citations(pinpoint)
                if not parsed_pinpoints:
                    continue
                index.add(
                    kind="maine_statute",
                    normalized_citation=parsed_pinpoints[0].normalized,
                    source_id=record.canonical_source_id,
                    authority_status=record.authority_status,
                    metadata={
                        "snapshot_source_id": record.snapshot_source_id,
                        "title": record.title,
                        "source_class": record.source_class,
                        "authority_kind": record.authority_kind,
                        "freshness_status": record.freshness_status,
                        "source_hash": record.source_hash,
                        "source_span": pinpoint_span,
                        "pinpoint": pinpoint,
                    },
                )
        return index

    def build_authority_graph(
        self,
        records: list[ParsedAuthorityRecord] | None = None,
        index: SourceAuthorityIndex | None = None,
    ) -> AuthorityGraph:
        records = records or load_parsed_authority_records(self.data_root)
        index = index or self.build_source_authority_index(records)
        graph = AuthorityGraph()
        for record in records:
            for citation in extract_citations(record.searchable_text()):
                resolution = index.resolve(citation)
                if resolution.status != "found" or not resolution.source_id:
                    continue
                if resolution.source_id == record.canonical_source_id:
                    continue
                relation = self._relation_for(record, citation)
                graph.add_authority_relation(
                    record.canonical_source_id,
                    resolution.source_id,
                    relation=relation,
                    metadata={
                        "raw_citation": citation.raw,
                        "normalized_citation": citation.normalized,
                        "citation_kind": citation.kind,
                        "source_authority_kind": record.authority_kind,
                        "negative_treatment_status": "negative_treatment_unknown"
                        if "opinion" in record.authority_kind
                        else None,
                    },
                )
        return graph

    def build(self, *, write: bool = True) -> dict[str, Any]:
        records = load_parsed_authority_records(self.data_root)
        index = self.build_source_authority_index(records)
        graph = self.build_authority_graph(records, index)
        source_cards = [record.source_card() for record in records]
        citation_rows = index.to_rows()
        graph_rows = [edge for edges in graph.to_adjacency().values() for edge in edges]
        report = {
            "status": "pass" if records else "blocked",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_root": str(self.data_root),
            "record_count": len(records),
            "citation_index_count": len(citation_rows),
            "authority_graph_edge_count": len(graph_rows),
            "source_card_count": len(source_cards),
            "negative_treatment_framework": "placeholder_unknown_until_licensed_citator_or_attorney_review",
            "outputs": {
                "citation_index": str(self.authority_layer_dir / "citation_index.json"),
                "authority_graph": str(self.authority_layer_dir / "authority_graph.json"),
                "source_cards": str(self.authority_layer_dir / "source_cards.jsonl"),
                "build_report": str(self.authority_layer_dir / "authority_layer_report.json"),
            },
        }
        if write:
            self.authority_layer_dir.mkdir(parents=True, exist_ok=True)
            (self.authority_layer_dir / "citation_index.json").write_text(
                json.dumps(citation_rows, indent=2, sort_keys=True), encoding="utf-8"
            )
            (self.authority_layer_dir / "authority_graph.json").write_text(
                json.dumps(graph.to_adjacency(), indent=2, sort_keys=True), encoding="utf-8"
            )
            with (self.authority_layer_dir / "source_cards.jsonl").open("w", encoding="utf-8") as fh:
                for card in source_cards:
                    fh.write(json.dumps(card, sort_keys=True) + "\n")
            (self.authority_layer_dir / "authority_layer_report.json").write_text(
                json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
            )
        return report

    @staticmethod
    def _relation_for(record: ParsedAuthorityRecord, citation: ParsedCitation) -> str:
        kind = record.authority_kind
        if "opinion" in kind and citation.kind == "maine_statute":
            return "case_cites_statute"
        if "opinion" in kind and citation.kind == "maine_rule":
            return "case_applies_rule"
        if "opinion" in kind and citation.kind == "maine_case":
            return "case_cites_case"
        if "form" in kind and citation.kind in {"maine_statute", "maine_rule", "federal_statute"}:
            return "form_depends_on_authority"
        if "rule" in kind and citation.kind == "maine_statute":
            return "rule_depends_on_statute"
        if "standing" in kind or "policy" in kind:
            return "standing_order_modifies_workflow"
        return "cites"
