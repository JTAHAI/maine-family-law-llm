"""Citation-aware chunking for statutes, rules, forms, and guides."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re

from .normalize import NormalizedDocument


HEADING_RE = re.compile(r"^(#{1,6}\s+.+|(?:§|Rule\s+|FM-)\S.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    title: str
    source_type: str
    official: bool
    url: str
    citation_hint: str
    effective_date: str
    version_label: str
    source_priority: int
    heading_path: tuple[str, ...]
    text: str
    start_hint: str
    end_hint: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["heading_path"] = list(self.heading_path)
        return payload


def chunk_document(document: NormalizedDocument, *, max_chars: int = 1400) -> list[Chunk]:
    sections = _split_sections(document.text)
    chunks: list[Chunk] = []
    for heading_path, section_text in sections:
        for part_index, part in enumerate(_split_long_section(section_text, max_chars=max_chars), start=1):
            clean = part.strip()
            if not clean:
                continue
            heading = " > ".join(heading_path) or document.title
            chunk_id = stable_chunk_id(document.source_id, heading, part_index, clean)
            lines = [line for line in clean.splitlines() if line.strip()]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source_id=document.source_id,
                    title=document.title,
                    source_type=document.source_type,
                    official=document.official,
                    url=document.url,
                    citation_hint=document.citation_hint,
                    effective_date=document.effective_date,
                    version_label=document.version_label,
                    source_priority=int(document.metadata.get("source_priority", 100) or 100),
                    heading_path=tuple(heading_path),
                    text=clean,
                    start_hint=lines[0][:120] if lines else "",
                    end_hint=lines[-1][:120] if lines else "",
                )
            )
    return chunks


def stable_chunk_id(source_id: str, heading: str, part_index: int, text: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{heading}|{part_index}|{text[:300]}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{digest}"


def _split_sections(text: str) -> list[tuple[list[str], str]]:
    current_heading: list[str] = []
    current_lines: list[str] = []
    sections: list[tuple[list[str], str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if HEADING_RE.match(stripped) and current_lines:
            sections.append((current_heading[:], "\n".join(current_lines)))
            current_lines = []
        if HEADING_RE.match(stripped):
            current_heading = [stripped.lstrip("#").strip()]
        current_lines.append(line)
    if current_lines:
        sections.append((current_heading[:], "\n".join(current_lines)))
    return sections


def _split_long_section(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in re.split(r"\n\s*\n", text):
        para_len = len(para)
        if current and current_len + para_len > max_chars:
            parts.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len
    if current:
        parts.append("\n\n".join(current))
    return parts
