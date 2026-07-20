"""Privacy-safe reviewer handoff projections for source cards and chat metadata."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any, Iterable

_SENSITIVE_PATTERNS = {
    "social_security_number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email_address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone_number": re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"),
    "date_of_birth_label": re.compile(r"\b(?:DOB|date of birth)\s*[:#-]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I),
}
_PATH_KEYS = {"path", "file_path", "absolute_path", "snapshot_path", "local_path"}
_TEXT_KEYS = {"text", "text_content", "raw_text", "full_text"}


def sensitive_categories(text: str) -> list[str]:
    return [name for name, pattern in _SENSITIVE_PATTERNS.items() if pattern.search(str(text or ""))]


def redact_sensitive_text(text: str, *, max_length: int = 480) -> str:
    value = str(text or "")
    for name, pattern in _SENSITIVE_PATTERNS.items():
        value = pattern.sub(f"[redacted:{name}]", value)
    value = " ".join(value.split())
    return value[:max_length].rstrip()


def _basename(value: object) -> str:
    raw = str(value or "").replace("\\", "/")
    return PurePath(raw).name if raw else ""


def build_handoff_safe_source_card(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    lane = str(metadata.get("source_lane") or "legal_authority")
    snippet = str(item.get("snippet") or metadata.get("text_excerpt") or "")
    categories = sensitive_categories(snippet)
    private = lane == "private_record"

    safe_metadata: dict[str, Any] = {}
    allow = {
        "source_lane", "authority_status", "freshness_status", "current_law_verified",
        "support_capability", "jurisdiction", "source_type", "source_class", "official",
        "page_number", "match_type", "ocr_derived", "trust_boundary",
        "instruction_like_text_detected", "instruction_like_findings",
    }
    for key in allow:
        if key in metadata:
            safe_metadata[key] = metadata[key]
    locator = _basename(metadata.get("source_locator") or metadata.get("path") or "")
    if locator:
        safe_metadata["source_locator_basename"] = locator
    safe_metadata["sensitive_data_categories"] = categories
    safe_metadata["private_content_omitted_by_default"] = private

    return {
        "source_id": str(item.get("source_id") or metadata.get("id") or "source"),
        "title": str(item.get("title") or metadata.get("title") or "Source")[:240],
        "citation": str(item.get("citation") or metadata.get("citation_hint") or "")[:240],
        "snippet": "[private record excerpt omitted from default handoff]" if private else redact_sensitive_text(snippet),
        "metadata": safe_metadata,
    }


def build_handoff_safe_source_cards(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_handoff_safe_source_card(dict(item)) for item in items]


def strip_unsafe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).casefold()
        if lowered in _PATH_KEYS or lowered in _TEXT_KEYS:
            continue
        if isinstance(item, dict):
            safe[key] = strip_unsafe_metadata(item)
        elif isinstance(item, list):
            safe[key] = [strip_unsafe_metadata(entry) if isinstance(entry, dict) else entry for entry in item[:50]]
        elif isinstance(item, str):
            safe[key] = redact_sensitive_text(item, max_length=800)
        else:
            safe[key] = item
    return safe
