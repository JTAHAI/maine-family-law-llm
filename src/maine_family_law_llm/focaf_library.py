"""Bundled FOCAF family-printable resources.

These are optional public family resources, never legal authority and never
private matter evidence.  Search is local and operates on build-time extracted
PDF page text stored in the checked-in public inventory.
"""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


RESOURCE_RELATIVE = Path("resources") / "focaf"
INVENTORY_NAME = "focaf_inventory.json"


def resource_root() -> Path:
    candidates = [Path(__file__).resolve().parent / RESOURCE_RELATIVE]
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        root = Path(frozen_root)
        candidates.extend(
            [
                root / "maine_family_law_llm" / RESOURCE_RELATIVE,
                root / "src" / "maine_family_law_llm" / RESOURCE_RELATIVE,
            ]
        )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError("focaf_resources_missing")


@lru_cache(maxsize=1)
def load_inventory() -> dict[str, Any]:
    path = resource_root() / INVENTORY_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "maine_family_law_llm.focaf_inventory.v1":
        raise RuntimeError("focaf_inventory_schema_invalid")
    return payload


def _terms(query: str) -> list[str]:
    stopwords = {"about", "and", "for", "from", "help", "i", "me", "my", "the", "to", "what", "with"}
    return [term.lower() for term in re.findall(r"[A-Za-z0-9']{2,}", query) if term.lower() not in stopwords]


def _query_phrase(query: str) -> str:
    quoted = re.search(r'"([^\"]+)"', query)
    return (quoted.group(1) if quoted else query).strip().lower()


def public_printable_view(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "title": document["display_title"],
        "description": document["description"],
        "category": document["category"],
        "audience": document["intended_audience"],
        "likely_use_cases": document["likely_use_cases"],
        "county": document.get("county", ""),
        "municipality": document.get("municipality", ""),
        "page_count": document["page_count"],
        "source_hash": document["source_hash"],
        "resource_lane": "family_printable_secondary_resource",
        "authority_status": "not_legal_authority",
        "open_path": f"/api/printables/{document['document_id']}/open",
        "preview_path": f"/api/printables/{document['document_id']}",
        "warnings": document.get("warnings", []),
    }


def get_printable(document_id: str) -> dict[str, Any] | None:
    for document in load_inventory().get("documents", []):
        if document.get("document_id") == document_id:
            return document
    return None


def printable_pdf_path(document_id: str) -> Path | None:
    document = get_printable(document_id)
    if document is None:
        return None
    path = resource_root() / str(document["original_filename"])
    return path if path.is_file() else None


def search_printables(query: str, limit: int = 4) -> dict[str, Any]:
    """Search actual extracted page text; filename-only matches are rejected."""

    query_terms = _terms(query)
    phrase = _query_phrase(query)
    if not query_terms:
        return {"query": query, "exact_phrase": phrase, "exact_content_match": False, "results": []}
    scored: list[tuple[int, dict[str, Any], list[dict[str, Any]], bool]] = []
    for document in load_inventory().get("documents", []):
        text_chunks = document.get("chunks", [])
        matched_chunks: list[dict[str, Any]] = []
        exact_content = False
        score = 0
        for chunk in text_chunks:
            text = str(chunk.get("text", "")).lower()
            if not text:
                continue
            term_count = sum(1 for term in query_terms if term in text)
            phrase_match = len(phrase) >= 3 and phrase in text
            if phrase_match or term_count:
                matched_chunks.append(chunk)
                score += term_count * 5 + (12 if phrase_match else 0)
                exact_content = exact_content or phrase_match
        if not matched_chunks:
            continue
        title_text = " ".join(
            [document["display_title"], document["category"], " ".join(document.get("headings", []))]
        ).lower()
        score += sum(2 for term in query_terms if term in title_text)
        scored.append((score, document, matched_chunks, exact_content))
    scored.sort(key=lambda row: (-row[0], row[1]["display_title"]))
    results = []
    for score, document, chunks, exact_content in scored[: max(1, min(limit, 6))]:
        first = chunks[0]
        view = public_printable_view(document)
        view.update(
            {
                "score": score,
                "exact_content_match": exact_content,
                "matched_pages": sorted({int(chunk["page_number"]) for chunk in chunks}),
                "snippet": str(first.get("text", ""))[:360],
                "why_relevant": f"Matched {len(chunks)} extracted page text segment(s) for your request.",
            }
        )
        results.append(view)
    return {
        "query": query,
        "exact_phrase": phrase,
        "exact_content_match": any(item["exact_content_match"] for item in results),
        "results": results,
        "resource_lane": "family_printable_secondary_resource",
        "authority_status": "not_legal_authority",
    }


def suggest_printables(question: str, limit: int = 3) -> list[dict[str, Any]]:
    return search_printables(question, limit=limit)["results"]
