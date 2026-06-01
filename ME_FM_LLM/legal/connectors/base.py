from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class SourceTarget:
    target_id: str
    source_class: str
    jurisdiction: str
    url: str
    parser_name: str
    expected_content_type: str = "text/html"
    priority: int = 1
    freshness_strategy: str = "retrieved_timestamp"
    notes: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        for field_name in ("target_id", "source_class", "jurisdiction", "url", "parser_name"):
            if not getattr(self, field_name):
                problems.append(f"missing {field_name}")
        if self.jurisdiction.lower() != "maine" and not self.jurisdiction.lower().startswith("federal"):
            problems.append("jurisdiction must be maine or federal-adjacent")
        if not self.url.startswith(("https://", "http://")):
            problems.append("url must be http(s)")
        return problems


@dataclass(frozen=True)
class RetrievedSource:
    target: SourceTarget
    content: bytes
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: str | None = None
    status_code: int | None = None
    final_url: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class ParserAuditEvent:
    source_id: str
    parser_name: str
    parser_version: str
    status: str
    message: str
    extracted_count: int = 0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "status": self.status,
            "message": self.message,
            "extracted_count": self.extracted_count,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class SourceFetcher(Protocol):
    def fetch(self, target: SourceTarget) -> RetrievedSource:
        ...
