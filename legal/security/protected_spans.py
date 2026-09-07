"""Offset-preserving privacy exclusions for model context and excerpt output.

Host/reviewer exclusions are authoritative even for otherwise unclassified
values. Label detection is a conservative extra defense, not a PII guarantee.
Original record previews are intentionally outside this projection.
"""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

_LABELED_VALUE = re.compile(
    r"(?im)\b(?:private\s+(?:reference(?:\s+string)?|identifier|id)|"
    r"personal\s+(?:access\s+)?(?:string|identifier|code)|"
    r"social\s+security(?:\s+number)?|ssn|account(?:\s+number)?|"
    r"routing(?:\s+number)?|password|passcode|api[\s_-]?key|access\s+token|"
    r"secret|medical\s+record(?:\s+number)?|mrn)\s*[:：﹕=–—-]\s*([^\r\n.;]+)"
)
_ANNOTATIONS = ("protected_spans", "privacy_exclusions", "redacted_spans")


def protected_spans(
    text: str, metadata: dict[str, Any] | None = None
) -> tuple[tuple[int, int], ...]:
    """Malformed/stale exclusions protect the whole source, never get ignored."""
    metadata = metadata or {}
    spans = [(match.start(1), match.end(1)) for match in _LABELED_VALUE.finditer(text)]
    if (
        metadata.get("exclude_from_model") is not None
        and metadata["exclude_from_model"] is not False
    ):
        return ((0, len(text)),)
    for key in _ANNOTATIONS:
        rows = metadata.get(key, [])
        if not isinstance(rows, (tuple, list)):
            return ((0, len(text)),)
        for row in rows:
            if not isinstance(row, dict):
                return ((0, len(text)),)
            start, end = row.get("start_offset"), row.get("end_offset")
            expected = row.get("source_text_sha256")
            if (
                type(start) is not int
                or type(end) is not int
                or not 0 <= start < end <= len(text)
                or (expected is not None and expected != sha256(text.encode("utf-8")).hexdigest())
            ):
                return ((0, len(text)),)
            spans.append((start, end))
    return tuple(sorted(set(spans)))


def overlaps_protected_span(start: int, end: int, text: str, metadata=None) -> bool:
    return any(start < right and end > left for left, right in protected_spans(text, metadata))


def model_context_projection(text: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    spans = protected_spans(text, metadata)
    if not spans:
        return text, metadata
    projected = list(text)
    for start, end in spans:
        for offset in range(start, end):
            if not projected[offset].isspace():
                projected[offset] = "█"
    result = "".join(projected)
    # Carry the exclusions into output verification, including for model-selected
    # mask characters. Bind the new offsets to the exact transmitted projection.
    updated = {key: value for key, value in metadata.items() if key not in _ANNOTATIONS}
    updated["protected_spans"] = [
        {
            "start_offset": start,
            "end_offset": end,
            "source_text_sha256": sha256(result.encode("utf-8")).hexdigest(),
        }
        for start, end in spans
    ]
    updated["privacy_projection"] = "protected_values_withheld"
    return result, updated
