"""Citation rendering helpers."""

from __future__ import annotations

from typing import Any


def render_citation_item(item: Any, index: int | None = None) -> str:
    prefix = f"[{index}] " if index is not None else ""
    title = getattr(item, "title", "") or _meta(item, "title") or "Untitled source"
    source_type = getattr(item, "source_type", "") or _meta(item, "source_type")
    url = getattr(item, "url", "") or _meta(item, "url")
    hint = getattr(item, "citation_hint", "") or _meta(item, "citation_hint")
    effective = getattr(item, "effective_date", "") or _meta(item, "effective_date")
    version = getattr(item, "version_label", "") or _meta(item, "version_label")
    parts = [prefix + str(title)]
    if source_type:
        parts.append(f"type={source_type}")
    if hint:
        parts.append(f"citation={hint}")
    if effective:
        parts.append(f"effective_date={effective}")
    if version:
        parts.append(f"version={version}")
    if url:
        parts.append(str(url))
    return " | ".join(parts)


def render_citation_appendix(items: list[Any] | tuple[Any, ...]) -> str:
    if not items:
        return "Citation appendix: no sources retrieved."
    lines = ["Citation appendix:"]
    for index, item in enumerate(items, start=1):
        lines.append(render_citation_item(item, index=index))
    return "\n".join(lines)


def _meta(item: Any, key: str) -> str:
    metadata = getattr(item, "metadata", {}) or {}
    if isinstance(metadata, dict):
        return str(metadata.get(key, "") or "")
    return ""
