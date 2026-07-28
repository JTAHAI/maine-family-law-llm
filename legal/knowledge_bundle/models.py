from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_CONCEPT_SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


class KnowledgeBundleError(ValueError):
    pass


def parse_concept_id(value: str) -> tuple[str, ...]:
    parts = tuple(part for part in value.split("/") if part)
    if not parts:
        raise KnowledgeBundleError("empty concept id")
    for part in parts:
        if not _CONCEPT_SEGMENT_RE.fullmatch(part):
            raise KnowledgeBundleError(f"invalid concept id segment: {part!r}")
    return parts


@dataclass(frozen=True)
class KnowledgeConcept:
    concept_id: str
    type: str
    title: str
    body: str
    description: str = ""
    resource: str = ""
    tags: tuple[str, ...] = ()
    timestamp: str = ""
    citations: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parse_concept_id(self.concept_id)
        if not self.type.strip():
            raise KnowledgeBundleError("concept type is required")
        if not self.title.strip():
            raise KnowledgeBundleError("concept title is required")
        if len(self.body.encode("utf-8")) > 5 * 1024 * 1024:
            raise KnowledgeBundleError("concept body exceeds 5 MiB")

    def frontmatter(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
        }
        if self.description:
            payload["description"] = self.description
        if self.resource:
            payload["resource"] = self.resource
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.timestamp:
            payload["timestamp"] = self.timestamp
        if self.citations:
            payload["citations"] = list(self.citations)
        for key, value in sorted(self.metadata.items()):
            if key not in payload:
                payload[key] = value
        return payload
