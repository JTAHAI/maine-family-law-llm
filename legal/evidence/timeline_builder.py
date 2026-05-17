from __future__ import annotations

from datetime import datetime
from typing import Any

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y")


def _sort_key(value: str | None) -> tuple[int, str]:
    if not value or value == "unknown":
        return (1, "9999-12-31")
    for fmt in DATE_FORMATS:
        try:
            return (0, datetime.strptime(value, fmt).date().isoformat())
        except ValueError:
            continue
    return (1, value)


class TimelineBuilder:
    def build(self, events: list[dict[str, Any]]):
        normalized = []
        for index, event in enumerate(events):
            normalized.append({
                "event_id": event.get("event_id", f"event_{index}"),
                "matter_id": event.get("matter_id"),
                "date": event.get("date", "unknown"),
                "description": event.get("description", ""),
                "source_document_id": event.get("source_document_id"),
                "span_start": event.get("span_start"),
                "span_end": event.get("span_end"),
                "confidence": event.get("confidence", 0.5),
                "review_required": True,
            })
        return sorted(normalized, key=lambda item: _sort_key(item.get("date")))
