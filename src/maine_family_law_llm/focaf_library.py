"""Bundled FOCAF family-printable resources.

These are optional public family resources, never legal authority and never
private matter evidence. Search is local and operates on build-time extracted
PDF page text stored in the checked-in public inventory.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


RESOURCE_RELATIVE = Path("resources") / "focaf"
INVENTORY_NAME = "focaf_inventory.json"


class PrintableAssetError(RuntimeError):
    """A known printable cannot be safely opened from the packaged assets."""

    def __init__(self, code: str, document_id: str, *, expected_path: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.document_id = document_id
        self.expected_path = expected_path


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve(strict=False)).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def resource_roots() -> list[Path]:
    """Return all plausible FOCAF resource roots in safe priority order.

    Frozen builds intentionally prefer the packaged ``maine_family_law_llm``
    data directory before the copied source tree. The v3.1.1 package contained
    the inventory in both places but the PDF bytes only in the packaged data
    directory; selecting the source-tree directory caused every ``/open``
    request to fail even though the PDFs were present in the MSIX.
    """

    candidates: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        root = Path(frozen_root)
        candidates.extend(
            [
                root / "maine_family_law_llm" / RESOURCE_RELATIVE,
                root / "src" / "maine_family_law_llm" / RESOURCE_RELATIVE,
            ]
        )
    candidates.append(Path(__file__).resolve().parent / RESOURCE_RELATIVE)
    return [path for path in _dedupe_paths(candidates) if path.is_dir()]


def resource_root() -> Path:
    """Return the best root for inventory reads.

    Prefer a directory that contains both the inventory and at least one PDF.
    This prevents a partial duplicate data tree from shadowing the complete
    packaged asset directory.
    """

    roots = resource_roots()
    for candidate in roots:
        if (candidate / INVENTORY_NAME).is_file() and any(candidate.glob("*.pdf")):
            return candidate
    for candidate in roots:
        if (candidate / INVENTORY_NAME).is_file():
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
    stopwords = {
        "about", "all", "and", "are", "can", "do", "for", "from", "help",
        "how", "i", "in", "is", "me", "my", "of", "the", "to", "was",
        "what", "when", "where", "with", "would", "you",
    }
    return list(
        dict.fromkeys(
            term.lower()
            for term in re.findall(r"[A-Za-z0-9']{2,}", query)
            if term.lower() not in stopwords
        )
    )


def _query_phrase(query: str) -> str:
    quoted = re.search(r'"([^\"]+)"', query)
    return (quoted.group(1) if quoted else query).strip().lower()


PRACTICAL_INTENT_RULES: tuple[dict[str, Any], ...] = (
    {
        "intent": "served_or_starting",
        "triggers": ("served", "summons", "court papers", "before i call", "before i file", "where do i start"),
        "expand": ("served", "papers", "summons", "deadline", "court", "file", "organize"),
        "preferred": (("before-you-call-or-file", 90), ("parent-quick-start", 75), ("court-day-bag", 55)),
    },
    {
        "intent": "court_day",
        "triggers": ("bring to court", "court day", "prepare for court", "hearing bag", "what to bring"),
        "expand": ("court", "hearing", "papers", "questions", "transportation", "childcare", "checklist"),
        "preferred": (("court-day-bag", 110), ("before-you-call-or-file", 45), ("after-the-hearing", 25)),
    },
    {
        "intent": "exchange_medication",
        "triggers": ("exchange medication", "medication transfer", "belongings transfer", "handoff medication"),
        "expand": ("exchange", "handoff", "medication", "belongings", "transfer"),
        "preferred": (("belongings-medication-transfer", 120), ("handoff-exchange-notes", 80)),
    },
    {
        "intent": "school_update",
        "triggers": ("school update", "childcare update", "provider update", "teacher update", "school provider"),
        "expand": ("school", "childcare", "provider", "update", "teacher", "care team"),
        "preferred": (("family-update-sheet-school-childcare", 120), ("provider-update-guide", 90), ("school-provider-one-page", 75), ("school-care-team", 65)),
    },
    {
        "intent": "calm_communication",
        "triggers": ("calm message", "rewrite message", "communication", "de-escalate", "neutral message"),
        "expand": ("calm", "message", "communication", "brief", "neutral", "child-focused"),
        "preferred": (("calm-communication-mini", 120), ("calm-communication-pack", 110), ("handoff-exchange-notes", 55)),
    },
    {
        "intent": "deadlines",
        "triggers": ("track deadlines", "deadline tracker", "orders dates", "court dates", "due dates"),
        "expand": ("orders", "dates", "deadlines", "tracker", "hearing", "service"),
        "preferred": (("orders-dates-deadlines", 130), ("before-you-call-or-file", 45)),
    },
    {
        "intent": "best_interest",
        "triggers": ("best interest", "best-interest", "19-a factors", "1653 factors"),
        "expand": ("best", "interest", "factors", "child", "planner", "19-a", "1653"),
        "preferred": (("19a-best-interest-factors-parent-planner", 140), ("child-wellbeing-observation", 70)),
    },
    {
        "intent": "teen_or_two_homes",
        "triggers": ("teen two homes", "teen guide", "two homes", "two-home", "child routine across homes"),
        "expand": ("teen", "two", "home", "homes", "routine", "transition", "school", "trusted adults"),
        "preferred": (("teen-guide", 130), ("two-home-routine", 125), ("weekly-routine-school-planner", 65)),
    },
    {
        "intent": "grandparent_helper",
        "triggers": ("grandparent helper", "grandparent guide", "relative helper", "family helper"),
        "expand": ("grandparent", "relative", "helper", "caregiver", "support"),
        "preferred": (("grandparent-helper", 140), ("parent-helper-packet", 45)),
    },
    {
        "intent": "local_resources",
        "triggers": ("family resources", "local resources", "resource sheet", "support contacts"),
        "expand": ("family", "resources", "local", "support", "contacts", "quick sheet"),
        "preferred": (("family-resource-quick-sheet", 80),),
    },
)

RESEARCH_OR_POLICY_FILENAMES = (
    "family-court-delay-intergenerational-harm",
    "family-harms-executive-summary",
    "maine-parental-rights-best-interest-family-court-process",
    "restoring-parent-child-relationships-after-disparagement-contact-refusal",
    "rfc-comment-template",
    "rfc-how-to-review",
    "officials-packet",
    "skeptic-packet",
    "research-source-index",
    "family-communication-systems-ai-guidance",
)


def _intent_profile(query: str) -> tuple[list[str], list[tuple[str, int]], list[str]]:
    lowered = query.lower()
    expansions: list[str] = []
    preferred: list[tuple[str, int]] = []
    intents: list[str] = []
    for rule in PRACTICAL_INTENT_RULES:
        if any(trigger in lowered for trigger in rule["triggers"]):
            intents.append(str(rule["intent"]))
            expansions.extend(str(term) for term in rule["expand"])
            preferred.extend((str(token), int(boost)) for token, boost in rule["preferred"])
    return list(dict.fromkeys(expansions)), preferred, intents


def _preferred_boost(filename: str, preferred: list[tuple[str, int]]) -> int:
    lowered = filename.lower()
    return max((boost for token, boost in preferred if token in lowered), default=0)


def _research_penalty(document: dict[str, Any], query: str) -> int:
    lowered_query = query.lower()
    if any(term in lowered_query for term in ("research", "policy", "initiative", "executive summary", "study", "sources")):
        return 0
    filename = str(document.get("original_filename") or "").lower()
    return 90 if any(token in filename for token in RESEARCH_OR_POLICY_FILENAMES) else 0


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def printable_pdf_path(document_id: str, *, verify_hash: bool = True) -> Path | None:
    """Resolve a known printable across all packaged resource roots.

    ``None`` is reserved for an unknown document ID for backward compatibility.
    Known inventory rows with missing or modified bytes raise a typed error so
    the API does not hide a defective package behind a generic 404.
    """

    document = get_printable(document_id)
    if document is None:
        return None
    filename = str(document.get("original_filename") or "").strip()
    if not filename or Path(filename).name != filename:
        raise PrintableAssetError("printable_asset_path_invalid", document_id, expected_path=filename)
    for root in resource_roots():
        path = root / filename
        if not path.is_file():
            continue
        expected_hash = str(document.get("source_hash") or "").strip().lower()
        if verify_hash and expected_hash and _sha256_file(path).lower() != expected_hash:
            raise PrintableAssetError("printable_hash_mismatch", document_id, expected_path=filename)
        return path
    raise PrintableAssetError("printable_asset_missing", document_id, expected_path=filename)


def audit_packaged_printables(*, verify_hashes: bool = True) -> dict[str, Any]:
    """Fail-closed audit used by packaging tests and release smoke checks."""

    documents = list(load_inventory().get("documents", []))
    missing: list[str] = []
    mismatched: list[str] = []
    resolved: list[str] = []
    for document in documents:
        document_id = str(document.get("document_id") or "")
        try:
            path = printable_pdf_path(document_id, verify_hash=verify_hashes)
        except PrintableAssetError as exc:
            (mismatched if exc.code == "printable_hash_mismatch" else missing).append(document_id)
        else:
            if path is not None:
                resolved.append(document_id)
    return {
        "status": "pass" if not missing and not mismatched and len(resolved) == len(documents) else "fail",
        "expected": len(documents),
        "resolved": len(resolved),
        "missing": missing,
        "hash_mismatches": mismatched,
        "resource_roots": [str(path) for path in resource_roots()],
    }



def _printable_family_key(document: dict[str, Any]) -> str:
    stem = Path(str(document.get("original_filename") or "")).stem.lower()
    stem = re.sub(r"^focaf-", "", stem)
    stem = re.sub(r"-(?:public|guide(?:-v\d+)?|v\d+)$", "", stem)
    return stem

def search_printables(query: str, limit: int = 4) -> dict[str, Any]:
    """Search extracted content with practical-family ranking.

    Every returned item must still contain a content match. Metadata and intent
    signals only rerank those content-backed candidates, so a filename alone
    never becomes a search hit. Long research PDFs cannot dominate merely by
    repeating common words across many pages.
    """

    base_terms = _terms(query)
    expanded_terms, preferred, intents = _intent_profile(query)
    query_terms = list(dict.fromkeys([*base_terms, *expanded_terms]))
    phrase = _query_phrase(query)
    if not query_terms:
        return {
            "query": query,
            "exact_phrase": phrase,
            "exact_content_match": False,
            "results": [],
            "matched_intents": intents,
        }

    scored: list[tuple[int, dict[str, Any], list[dict[str, Any]], bool, list[str]]] = []
    for document in load_inventory().get("documents", []):
        text_chunks = list(document.get("chunks", []))
        matched_chunks: list[dict[str, Any]] = []
        exact_content = False
        best_chunk_score = 0
        matched_terms: set[str] = set()
        for chunk in text_chunks:
            text = str(chunk.get("text", "")).lower()
            if not text:
                continue
            chunk_terms = {term for term in query_terms if term in text}
            phrase_match = len(phrase) >= 3 and phrase in text
            if not phrase_match and not chunk_terms:
                continue
            matched_chunks.append(chunk)
            matched_terms.update(chunk_terms)
            exact_content = exact_content or phrase_match
            best_chunk_score = max(
                best_chunk_score,
                len(chunk_terms) * 10 + (28 if phrase_match else 0),
            )
        if not matched_chunks:
            continue

        title = str(document.get("display_title") or "")
        filename = str(document.get("original_filename") or "")
        metadata_text = " ".join(
            [
                title,
                str(document.get("description") or ""),
                str(document.get("category") or ""),
                str(document.get("intended_audience") or ""),
                " ".join(str(value) for value in document.get("likely_use_cases", [])),
                str(document.get("county") or ""),
                str(document.get("municipality") or ""),
                " ".join(str(value) for value in document.get("headings", [])),
            ]
        ).lower()
        title_text = f"{title} {filename}".lower()
        metadata_matches = {term for term in query_terms if term in metadata_text}
        title_matches = {term for term in query_terms if term in title_text}
        score = (
            best_chunk_score
            + min(len(matched_chunks), 5) * 2
            + len(metadata_matches) * 5
            + len(title_matches) * 12
            + _preferred_boost(filename, preferred)
            - _research_penalty(document, query)
        )

        # A municipality named by the user should strongly favor its exact
        # quick sheet over statewide or research materials.
        municipality = str(document.get("municipality") or "").strip().lower()
        county = str(document.get("county") or "").strip().lower()
        lowered_query = query.lower()
        if municipality and re.search(rf"(?<!\w){re.escape(municipality)}(?!\w)", lowered_query):
            score += 140
        if county and county in lowered_query:
            score += 55
        if "family-resource-quick-sheet" in filename and "local_resources" in intents:
            score += 45

        scored.append((score, document, matched_chunks, exact_content, sorted(matched_terms)))

    scored.sort(key=lambda row: (-row[0], row[1]["display_title"]))
    results: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for score, document, chunks, exact_content, matched_terms in scored:
        family_key = _printable_family_key(document)
        if family_key in seen_families:
            continue
        seen_families.add(family_key)
        # Prefer a chunk with the greatest visible term coverage rather than the
        # first page containing boilerplate.
        first = max(
            chunks,
            key=lambda chunk: sum(1 for term in query_terms if term in str(chunk.get("text", "")).lower()),
        )
        view = public_printable_view(document)
        view.update(
            {
                "score": score,
                "exact_content_match": exact_content,
                "matched_pages": sorted({int(chunk["page_number"]) for chunk in chunks}),
                "matched_terms": matched_terms,
                "snippet": str(first.get("text", ""))[:360],
                "why_relevant": (
                    f"Matched printable content for {', '.join(matched_terms[:6]) or 'your request'}"
                    + (f" and the {document.get('category')} use case." if document.get("category") else ".")
                ),
                "match_basis": "extracted_content_with_practical_metadata_reranking",
            }
        )
        results.append(view)
        if len(results) >= max(1, min(limit, 8)):
            break
    return {
        "query": query,
        "exact_phrase": phrase,
        "exact_content_match": any(item["exact_content_match"] for item in results),
        "results": results,
        "matched_intents": intents,
        "resource_lane": "family_printable_secondary_resource",
        "authority_status": "not_legal_authority",
    }


def suggest_printables(question: str, limit: int = 3) -> list[dict[str, Any]]:
    return search_printables(question, limit=limit)["results"]
