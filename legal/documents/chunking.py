from __future__ import annotations

import hashlib

from legal.documents.models import LegalChunk, SourceLocation


def _stable_chunk_id(parent_document_id: str, start: int, text: str) -> str:
    digest = hashlib.sha256(f"{parent_document_id}:{start}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"chunk-{digest}"


def chunk_text(
    *,
    document_id: str,
    source_id: str,
    text: str,
    url_or_path: str | None = None,
    citation: str | None = None,
    max_chars: int = 1500,
    overlap_chars: int = 150,
) -> list[LegalChunk]:
    """Create parent-aware chunks without losing source offsets.

    The chunker is intentionally deterministic and dependency-free. It prefers paragraph
    boundaries but falls back to hard character windows for long statutory/case text.
    """

    clean_text = text.strip()
    if not clean_text:
        return []
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and less than max_chars")

    chunks: list[LegalChunk] = []
    cursor = 0
    while cursor < len(clean_text):
        target_end = min(len(clean_text), cursor + max_chars)
        if target_end < len(clean_text):
            paragraph_break = clean_text.rfind("\n\n", cursor, target_end)
            sentence_break = clean_text.rfind(". ", cursor, target_end)
            split_at = max(paragraph_break, sentence_break)
            if split_at > cursor + max_chars // 3:
                target_end = split_at + (2 if split_at == paragraph_break else 1)

        chunk_body = clean_text[cursor:target_end].strip()
        if chunk_body:
            chunks.append(
                LegalChunk(
                    chunk_id=_stable_chunk_id(document_id, cursor, chunk_body),
                    parent_document_id=document_id,
                    source_location=SourceLocation(
                        source_id=source_id,
                        url_or_path=url_or_path,
                        parent_id=document_id,
                        start_offset=cursor,
                        end_offset=target_end,
                    ),
                    text=chunk_body,
                    citation=citation,
                )
            )
        if target_end >= len(clean_text):
            break
        cursor = max(target_end - overlap_chars, cursor + 1)

    return chunks
