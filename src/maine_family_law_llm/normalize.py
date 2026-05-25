"""Normalize fetched Maine legal source material into citation-friendly text."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
from typing import Any

from .fetch import FetchResult, safe_file_stem


@dataclass(frozen=True)
class NormalizedDocument:
    source_id: str
    title: str
    source_type: str
    official: bool
    url: str
    citation_hint: str
    effective_date: str
    version_label: str
    text: str
    metadata: dict[str, Any]


def normalize_fetch_result(result: FetchResult, *, output_dir: str | Path | None = None) -> NormalizedDocument:
    if not result.ok:
        raise ValueError(f"cannot normalize failed fetch: {result.failure_class}")
    metadata = dict(result.metadata or {})
    text = normalize_text(result.raw_text)
    title = str(metadata.get("title") or result.source_id)
    source_id = str(metadata.get("source_id") or result.source_id)
    normalized = NormalizedDocument(
        source_id=source_id,
        title=title,
        source_type=str(metadata.get("source_type") or ""),
        official=bool(metadata.get("official")),
        url=str(metadata.get("url") or ""),
        citation_hint=str(metadata.get("citation_hint") or ""),
        effective_date=str(metadata.get("effective_date") or ""),
        version_label=str(metadata.get("version_label") or ""),
        text=f"# {title}\n\nSource ID: {source_id}\nOfficial URL: {metadata.get('url')}\n\n{text}".strip() + "\n",
        metadata=metadata,
    )
    if output_dir is not None:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{safe_file_stem(source_id)}.normalized.md").write_text(
            normalized.text,
            encoding="utf-8",
        )
        payload = dict(metadata)
        payload["normalized"] = True
        (out_dir / f"{safe_file_stem(source_id)}.normalized.metadata.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    return normalized


def normalize_text(raw: str) -> str:
    text = str(raw)
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "\n" + ("#" * int(m.group(1))) + " " + _strip_tags(m.group(2)) + "\n", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|li|tr)>", "\n", text)
    text = _strip_tags(text)
    text = html.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()


def _strip_tags(value: str) -> str:
    return re.sub(r"(?is)<[^>]+>", " ", value)
