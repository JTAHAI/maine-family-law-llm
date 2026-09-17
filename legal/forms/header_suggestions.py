"""Deterministic, source-bound header suggestions for local form working copies.

This module intentionally does *not* use an LLM or try to complete a court
form.  It recognizes a small set of explicitly labelled caption fields from
already-imported local record text and returns review-required candidates with
the exact source line that produced each one.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable


_MAX_RECORDS = 30
_MAX_TEXT_PER_RECORD = 160_000
_MAX_VALUE = 240
_MAX_CANDIDATES = 80

_DOCKET = re.compile(
    r"(?im)^\s*(?:docket|case)\s*(?:number|no\.?|#)?\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9 .\-/]{1,78})\s*$"
)
_LABELLED = re.compile(
    r"(?im)^\s*(petitioner|plaintiff|respondent|defendant|court(?:\s+name)?)\s*(?:name)?\s*:\s*(.{1,240}?)\s*$"
)
_SPACE = re.compile(r"\s+")


def _safe_text(value: Any, *, limit: int) -> str:
    return _SPACE.sub(" ", str(value or "").replace("\x00", " ")).strip()[:limit]


def _safe_record_text(value: Any) -> str:
    return str(value or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")[:_MAX_TEXT_PER_RECORD]


def _normal_field(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")[:80]


def _field_kind(field: str) -> str:
    normalized = _normal_field(field)
    if any(token in normalized for token in ("docket", "case_number", "case_no", "case_id")):
        return "docket"
    if "petitioner" in normalized or "plaintiff" in normalized:
        return "petitioner"
    if "respondent" in normalized or "defendant" in normalized:
        return "respondent"
    if normalized in {"court", "court_name", "court_location"} or normalized.startswith("court_"):
        return "court"
    return ""


def _candidate_id(field_key: str, value: str, source_id: str, source_hash: str) -> str:
    material = "\x1f".join((field_key, value.casefold(), source_id, source_hash)).encode("utf-8")
    return "header_" + hashlib.sha256(material).hexdigest()[:24]


def _source_meta(row: dict[str, Any]) -> dict[str, Any]:
    source_id = _safe_text(row.get("evidence_id") or row.get("source_id") or row.get("record_id"), limit=160)
    return {
        "source_id": source_id,
        "source_hash": _safe_text(row.get("source_hash") or row.get("sha256"), limit=128),
        "source_title": _safe_text(row.get("title") or row.get("display_name") or "Local record", limit=240),
        "ocr_status": _safe_text(row.get("ocr_status") or "unknown", limit=80),
    }


def _append_candidate(
    output: list[dict[str, Any]],
    *,
    field_key: str,
    value: str,
    source: dict[str, Any],
    quote: str,
) -> None:
    value = _safe_text(value, limit=_MAX_VALUE)
    quote = _safe_text(quote, limit=360)
    if not value or not quote or not source["source_id"]:
        return
    lowered = value.casefold()
    if "ignore previous" in lowered or "system message" in lowered:
        return
    candidate_id = _candidate_id(field_key, value, source["source_id"], source["source_hash"])
    if any(item["suggestion_id"] == candidate_id for item in output):
        return
    output.append(
        {
            "suggestion_id": candidate_id,
            "field_key": field_key,
            "value": value,
            "source": dict(source),
            "exact_source_text": quote,
            "ocr_derived": str(source["ocr_status"]).casefold() not in {"", "unknown", "not_needed", "not_required"},
            "status": "candidate_review_required",
            "review_required": True,
        }
    )


def build_header_suggestions(
    records: Iterable[dict[str, Any]], *, allowed_fields: Iterable[str]
) -> dict[str, Any]:
    """Return deterministic header candidates for verified working-copy fields.

    Only exact labelled lines are eligible.  Missing record IDs, unsupported
    form fields, unlabelled text, and ambiguous values fail closed.
    """

    fields_by_kind: dict[str, list[str]] = defaultdict(list)
    for raw in allowed_fields:
        field = _normal_field(raw)
        kind = _field_kind(field)
        if field and kind and field not in fields_by_kind[kind]:
            fields_by_kind[kind].append(field)

    candidates: list[dict[str, Any]] = []
    selected_sources: list[str] = []
    for raw in list(records)[:_MAX_RECORDS]:
        if not isinstance(raw, dict):
            continue
        source = _source_meta(raw)
        if not source["source_id"]:
            continue
        selected_sources.append(source["source_id"])
        text = _safe_record_text(raw.get("text_content") or raw.get("ocr_text") or raw.get("text_excerpt"))
        if not text:
            continue
        for match in _DOCKET.finditer(text):
            quote = match.group(0)
            for field in fields_by_kind["docket"]:
                _append_candidate(candidates, field_key=field, value=match.group(1), source=source, quote=quote)
        for match in _LABELLED.finditer(text):
            label = _normal_field(match.group(1))
            kind = "court" if label.startswith("court") else ("petitioner" if label in {"petitioner", "plaintiff"} else "respondent")
            for field in fields_by_kind[kind]:
                _append_candidate(candidates, field_key=field, value=match.group(2), source=source, quote=match.group(0))
        if len(candidates) >= _MAX_CANDIDATES:
            break

    values_by_field: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        values_by_field[candidate["field_key"]].add(candidate["value"].casefold())
    for candidate in candidates:
        if len(values_by_field[candidate["field_key"]]) > 1:
            candidate["status"] = "conflict_review_required"
            candidate["conflict"] = True
        else:
            candidate["conflict"] = False

    blockers: list[str] = []
    if not selected_sources:
        blockers.append("selected_source_records_unavailable")
    if not fields_by_kind:
        blockers.append("supported_header_fields_not_present_in_selected_forms")
    if not candidates and not blockers:
        blockers.append("no_explicit_labelled_header_values_found")
    return {
        "schema_version": "maine_form_header_suggestions_v1",
        "status": "review_required" if candidates else "blocked",
        "suggestions": candidates[:_MAX_CANDIDATES],
        "selected_source_ids": selected_sources,
        "blockers": blockers,
        "review_required": True,
        "filing_ready": False,
        "notice": "Candidates come only from explicitly labelled local record text. OCR, conflicts, and every accepted value require human review before use in a working copy.",
    }
