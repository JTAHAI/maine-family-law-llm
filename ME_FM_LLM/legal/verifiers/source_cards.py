from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SourceCard:
    source_id: str
    title: str = ""
    citation: str | None = None
    source_class: str = "unknown"
    jurisdiction: str = "maine"
    authority_status: str = "stale_unknown"
    freshness_status: str = "unknown"
    source_url_or_path: str | None = None
    source_span: dict[str, Any] | None = None
    negative_treatment_status: str | None = None
    form_version_status: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SourceCard":
        return cls(
            source_id=str(value.get("source_id") or value.get("record_id") or ""),
            title=str(value.get("title") or value.get("name") or value.get("source_id") or ""),
            citation=value.get("citation"),
            source_class=str(value.get("source_class") or "unknown"),
            jurisdiction=str(value.get("jurisdiction") or "maine"),
            authority_status=str(value.get("authority_status") or value.get("status") or "stale_unknown"),
            freshness_status=str(value.get("freshness_status") or "unknown"),
            source_url_or_path=value.get("source_url_or_path") or value.get("url") or value.get("url_or_path"),
            source_span=dict(value.get("source_span") or {}),
            negative_treatment_status=value.get("negative_treatment_status"),
            form_version_status=value.get("form_version_status"),
            metadata={k: v for k, v in value.items() if k not in _SOURCE_CARD_FIELDS},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "citation": self.citation,
            "source_class": self.source_class,
            "jurisdiction": self.jurisdiction,
            "authority_status": self.authority_status,
            "freshness_status": self.freshness_status,
            "source_url_or_path": self.source_url_or_path,
            "source_span": self.source_span or {},
            "negative_treatment_status": self.negative_treatment_status,
            "form_version_status": self.form_version_status,
            "metadata": self.metadata or {},
        }


_SOURCE_CARD_FIELDS = {
    "source_id",
    "record_id",
    "title",
    "name",
    "citation",
    "source_class",
    "jurisdiction",
    "authority_status",
    "status",
    "freshness_status",
    "source_url_or_path",
    "url",
    "url_or_path",
    "source_span",
    "negative_treatment_status",
    "form_version_status",
}


class SourceCardStore:
    """Small source-card lookup used by verifier reports and API responses."""

    def __init__(self, cards: Iterable[SourceCard | dict[str, Any]] | None = None) -> None:
        self._cards: dict[str, SourceCard] = {}
        for card in cards or []:
            self.add(card)

    def add(self, card: SourceCard | dict[str, Any]) -> None:
        source_card = card if isinstance(card, SourceCard) else SourceCard.from_mapping(card)
        if source_card.source_id:
            self._cards[source_card.source_id] = source_card

    def get(self, source_id: str | None) -> dict[str, Any] | None:
        if not source_id:
            return None
        card = self._cards.get(source_id)
        return card.to_dict() if card else None

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {source_id: card.to_dict() for source_id, card in sorted(self._cards.items())}

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "SourceCardStore":
        store = cls()
        file_path = Path(path)
        if not file_path.exists():
            return store
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                store.add(json.loads(line))
        return store
