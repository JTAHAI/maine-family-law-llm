"""Immutable, matter-local evidence work products.

The engine operates only on already-indexed private-record rows supplied by the
host.  It creates review aids: timelines, exhibit indexes, contradiction
candidates, missing-record checklists, and contempt/enforcement event ledgers.
It never determines that an allegation is true or that contempt occurred.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Sequence

from legal.matter.consistency_review import SourceText, find_cross_document_conflicts

SCHEMA_VERSION = "evidence_work_product_v1"
ALGORITHM_VERSION = "v5.10.0"
WORK_PRODUCT_FOLDER = "19_EVIDENCE_WORK_PRODUCT"
MAX_RECORDS = 10_000
MAX_TOTAL_TEXT_CHARS = 30_000_000
MAX_RECORD_TEXT_CHARS = 500_000
MAX_EVENTS = 5_000
MAX_LEDGER_ROWS = 2_000
MAX_CONTRADICTIONS = 500
MAX_FOCUS_TERMS = 50
MAX_FOCUS_TERM_CHARS = 160
MAX_JSON_BYTES = 64 * 1024 * 1024

_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^\n.!?]+(?:[.!?]+|$)", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ORDER_TERMS = ("shall", "must", "is ordered", "ordered to", "required to", "may not", "prohibited from")
_NONCOMPLIANCE_TERMS = (
    "failed to", "did not", "has not", "have not", "refused to", "unpaid", "past due",
    "noncompliance", "non-compliance", "violat", "breach", "withheld", "denied contact",
)
_ENFORCEMENT_TERMS = (
    "contempt", "enforce", "enforcement", "noncompliance", "non-compliance", "violation",
    "order", "arrears", "past due", "failed to", "refused to", "did not comply",
)
_ASSERTION_ALLEGATION = ("allege", "assert", "claims", "states that", "reported", "accused")
_ASSERTION_COURT = ("the court finds", "court found", "the court orders", "it is ordered", "judgment", "decree")
_DATE_CUES = {
    "hearing_date": ("hearing", "trial", "conference", "mediation"),
    "service_date": ("served", "service", "summons", "received notice"),
    "filing_date": ("filed", "filing", "submitted to court"),
    "order_date": ("order", "judgment", "decree", "entered"),
    "payment_date": ("paid", "payment", "support", "arrears"),
    "message_timestamp": ("email", "text message", "message", "sent", "received"),
    "alleged_event_date": ("on", "occurred", "happened", "incident"),
}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has", "have",
    "he", "her", "hers", "him", "his", "i", "in", "is", "it", "its", "of", "on", "or", "she",
    "that", "the", "their", "them", "they", "this", "to", "was", "were", "will", "with", "you",
}
_ACTION_STEMS = {
    "pay", "compli", "attend", "deliver", "contact", "return", "provid", "allow", "follow", "sign",
    "file", "serv", "visit", "communicat", "transfer", "reimburs", "disclos", "appear", "respond",
}
_NEGATION_MARKERS = (" not ", " no ", " never ", "failed", "refused", "unpaid", "absent", "denied", "without")


class EvidenceWorkProductError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class EvidenceArtifact:
    name: str
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
        }


@dataclass
class EvidenceWorkProductResult:
    status: str
    build_id: str
    packet: dict[str, Any]
    artifacts: list[EvidenceArtifact] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reused_existing_build: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "build_id": self.build_id,
            "packet": self.packet,
            "artifacts": [item.as_dict() for item in self.artifacts],
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "reused_existing_build": self.reused_existing_build,
            "review_required": True,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_basename(value: Any) -> str:
    raw = str(value or "").replace("\x00", "").strip()
    visible = raw.rsplit("!", 1)[-1].split("#page=", 1)[0]
    name = PureWindowsPath(visible).name or Path(visible.replace("\\", "/")).name
    return (name or "record")[:240]


def _safe_title(value: Any, fallback: str) -> str:
    raw = str(value or "").replace("\x00", "").strip()
    if not raw:
        return fallback[:300]
    if "/" in raw or "\\" in raw:
        return _safe_basename(raw)[:300]
    return raw[:300]


def _clean_text(value: Any, *, limit: int = MAX_RECORD_TEXT_CHARS) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _record_text(row: dict[str, Any]) -> tuple[str, str]:
    for key in ("text", "derived_text", "content", "text_excerpt", "snippet"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value), key
    return "", "none"


def _normalize_date(value: str) -> str:
    raw = value.strip().replace("Sept.", "Sep.")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw.casefold()


def _sentence_rows(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _SENTENCE_RE.finditer(text):
        value = " ".join(match.group(0).split())
        if value:
            yield value, match.start(), match.end()


def _tokens(value: str) -> set[str]:
    output: set[str] = set()
    for token in _TOKEN_RE.findall(value.casefold()):
        if token in _STOPWORDS or len(token) < 2:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[: -len(suffix)]
                break
        output.add(token)
    return output


def _assertion_type(sentence: str) -> str:
    lowered = sentence.casefold()
    if any(term in lowered for term in _ASSERTION_COURT):
        return "court_or_order_language"
    if any(term in lowered for term in _ASSERTION_ALLEGATION):
        return "allegation_or_party_statement"
    return "record_statement"


def _date_type(sentence: str) -> str:
    lowered = sentence.casefold()
    ranked: list[tuple[int, str]] = []
    for label, cues in _DATE_CUES.items():
        score = sum(1 for cue in cues if cue in lowered)
        if score:
            ranked.append((score, label))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1] if ranked else "date_mentioned_in_record"


def _record_rows(records: Sequence[dict[str, Any]], selected_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    safe: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    total_chars = 0
    for raw in records[:MAX_RECORDS]:
        if not isinstance(raw, dict):
            continue
        evidence_id = str(raw.get("evidence_id") or raw.get("source_id") or "").strip()[:256]
        if not evidence_id or evidence_id in seen:
            continue
        if selected_ids and evidence_id not in selected_ids and str(raw.get("parent_evidence_id") or "") not in selected_ids:
            continue
        text, text_field = _record_text(raw)
        if not text:
            warnings.append(f"record_text_unavailable:{evidence_id}")
        if total_chars + len(text) > MAX_TOTAL_TEXT_CHARS:
            warnings.append("record_text_budget_exhausted")
            break
        total_chars += len(text)
        locator = raw.get("source_locator") or raw.get("source_path") or raw.get("filename") or raw.get("title")
        source_hash = str(raw.get("source_hash") or raw.get("sha256") or "").strip().lower()
        if source_hash and not re.fullmatch(r"[a-f0-9]{64}", source_hash):
            source_hash = ""
            warnings.append(f"invalid_source_hash:{evidence_id}")
        row = {
            "evidence_id": evidence_id,
            "parent_evidence_id": str(raw.get("parent_evidence_id") or "")[:256],
            "title": _safe_title(raw.get("title") or raw.get("subject"), evidence_id),
            "safe_filename": _safe_basename(locator),
            "source_type": _clean_text(raw.get("source_type") or raw.get("document_type") or "record", limit=80),
            "source_hash": source_hash,
            "text_sha256": _sha_bytes(text.encode("utf-8")),
            "text": text,
            "text_field": text_field,
            "page_number": max(0, int(raw.get("page_number") or 0)),
            "parser_status": _clean_text(raw.get("parser_status"), limit=80),
            "ocr_status": _clean_text(raw.get("ocr_status"), limit=80),
            "ocr_derived": bool(raw.get("ocr_derived")),
            "issue_lanes": list(raw.get("issue_lanes") or []) if isinstance(raw.get("issue_lanes"), list) else _clean_text(raw.get("issue_lanes"), limit=500).split(","),
            "duplicate_copy_count": max(1, int(raw.get("duplicate_copy_count") or 1)),
            "canonical_evidence_id": str(raw.get("canonical_evidence_id") or evidence_id)[:256],
            "privacy_status": _clean_text(raw.get("privacy_status"), limit=80),
            "span_basis": f"indexed_{text_field}",
        }
        safe.append(row)
        seen.add(evidence_id)
    safe.sort(key=lambda row: (row["safe_filename"].casefold(), row["page_number"], row["evidence_id"]))
    return safe, warnings


def _timeline(records: Sequence[dict[str, Any]], focus_terms: Sequence[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    focus = [term.casefold() for term in focus_terms if term]
    for record in records:
        text = record["text"]
        for sentence, start, end in _sentence_rows(text):
            if focus and not any(term in sentence.casefold() for term in focus):
                continue
            for date_match in _DATE_RE.finditer(sentence):
                normalized = _normalize_date(date_match.group(0))
                event_key = _sha_bytes(f"{normalized}\0{sentence.casefold()}\0{record['canonical_evidence_id']}".encode("utf-8"))
                if event_key in seen:
                    continue
                seen.add(event_key)
                events.append({
                    "event_id": f"event-{event_key[:16]}",
                    "date": normalized,
                    "displayed_date": date_match.group(0),
                    "date_type": _date_type(sentence),
                    "description": sentence[:2_000],
                    "assertion_type": _assertion_type(sentence),
                    "source": {
                        "evidence_id": record["evidence_id"],
                        "title": record["title"],
                        "safe_filename": record["safe_filename"],
                        "source_hash": record["source_hash"],
                        "page_number": record["page_number"],
                        "span_start": start,
                        "span_end": end,
                        "span_basis": record["span_basis"],
                    },
                    "confidence": 0.9 if record["text_field"] in {"text", "derived_text", "content"} else 0.65,
                    "review_required": True,
                    "does_not_prove": "The indexed record states or displays this date; that alone does not prove the event occurred as described.",
                })
                if len(events) >= MAX_EVENTS:
                    return sorted(events, key=lambda row: (row["date"], row["event_id"]))
    return sorted(events, key=lambda row: (row["date"], row["event_id"]))


def _contempt_ledger(records: Sequence[dict[str, Any]], timeline: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline_by_source: dict[str, list[dict[str, Any]]] = {}
    for event in timeline:
        timeline_by_source.setdefault(str(event.get("source", {}).get("evidence_id") or ""), []).append(event)
    rows: list[dict[str, Any]] = []
    for record in records:
        text = record["text"]
        if not any(term in text.casefold() for term in _ENFORCEMENT_TERMS):
            continue
        order_spans: list[dict[str, Any]] = []
        conduct_spans: list[dict[str, Any]] = []
        for sentence, start, end in _sentence_rows(text):
            lowered = sentence.casefold()
            span = {
                "text": sentence[:2_000],
                "span_start": start,
                "span_end": end,
                "span_basis": record["span_basis"],
                "page_number": record["page_number"],
            }
            if any(term in lowered for term in _ORDER_TERMS):
                order_spans.append(span)
            if any(term in lowered for term in _NONCOMPLIANCE_TERMS):
                conduct_spans.append(span)
        if not order_spans and not conduct_spans and "contempt" not in text.casefold() and "enforce" not in text.casefold():
            continue
        row_key = _sha_bytes(f"{record['evidence_id']}\0{record['text_sha256']}".encode("utf-8"))
        rows.append({
            "ledger_id": f"enforcement-{row_key[:16]}",
            "source": {
                "evidence_id": record["evidence_id"],
                "title": record["title"],
                "safe_filename": record["safe_filename"],
                "source_hash": record["source_hash"],
                "page_number": record["page_number"],
            },
            "timeline_event_ids": [event["event_id"] for event in timeline_by_source.get(record["evidence_id"], [])[:50]],
            "operative_order_language": order_spans[:20],
            "alleged_or_reported_conduct": conduct_spans[:20],
            "notice_or_service_status": "mentioned" if any(term in text.casefold() for term in ("served", "service", "notice")) else "not_established_from_selected_record",
            "ability_to_comply_information": "mentioned" if any(term in text.casefold() for term in ("ability to comply", "unable to", "cannot afford", "could not")) else "not_established_from_selected_record",
            "requested_relief": "mentioned" if any(term in text.casefold() for term in ("requests", "seeks", "relief", "sanction", "remedy")) else "not_established_from_selected_record",
            "missing_elements": [
                *([] if order_spans else ["exact_operative_order_language_not_found_in_selected_record"]),
                *([] if conduct_spans else ["specific_alleged_noncompliance_event_not_found_in_selected_record"]),
            ],
            "legal_conclusion": "not_determined",
            "review_required": True,
            "does_not_prove": "This row organizes record text only. It does not establish contempt, enforceability, notice, ability to comply, willfulness, or entitlement to relief.",
        })
        if len(rows) >= MAX_LEDGER_ROWS:
            break
    return rows


def _polarity_conflicts(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    sentence_rows: list[dict[str, Any]] = []
    for record in records:
        for sentence, start, end in _sentence_rows(record["text"]):
            tokens = _tokens(sentence)
            action_tokens = {token for token in tokens if any(token.startswith(stem) or stem.startswith(token) for stem in _ACTION_STEMS)}
            if not action_tokens or len(tokens) < 4:
                continue
            padded = f" {sentence.casefold()} "
            sentence_rows.append({
                "sentence": sentence,
                "tokens": tokens,
                "actions": action_tokens,
                "negative": any(marker in padded for marker in _NEGATION_MARKERS),
                "source": record,
                "span_start": start,
                "span_end": end,
            })
            if len(sentence_rows) >= 5_000:
                break
    conflicts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, left in enumerate(sentence_rows):
        for right in sentence_rows[index + 1 :]:
            if left["source"]["canonical_evidence_id"] == right["source"]["canonical_evidence_id"]:
                continue
            if left["negative"] == right["negative"]:
                continue
            shared_actions = left["actions"] & right["actions"]
            shared_tokens = left["tokens"] & right["tokens"]
            if not shared_actions or len(shared_tokens) < 3:
                continue
            key = _sha_bytes("\0".join(sorted((left["sentence"].casefold(), right["sentence"].casefold()))).encode("utf-8"))
            if key in seen:
                continue
            seen.add(key)
            conflicts.append({
                "conflict_id": f"polarity-{key[:16]}",
                "conflict_type": "opposing_record_language",
                "severity": "review_required",
                "shared_action_terms": sorted(shared_actions),
                "shared_context_terms": sorted(shared_tokens)[:30],
                "occurrences": [
                    {
                        "evidence_id": item["source"]["evidence_id"],
                        "title": item["source"]["title"],
                        "safe_filename": item["source"]["safe_filename"],
                        "source_hash": item["source"]["source_hash"],
                        "page_number": item["source"]["page_number"],
                        "span_start": item["span_start"],
                        "span_end": item["span_end"],
                        "text": item["sentence"][:2_000],
                        "polarity": "negative" if item["negative"] else "affirmative",
                        "span_basis": item["source"]["span_basis"],
                    }
                    for item in (left, right)
                ],
                "legal_significance": "not_determined",
                "review_required": True,
                "does_not_prove": "Opposing wording may reflect different dates, people, scopes, or contexts. Review the originals before treating this as a contradiction.",
            })
            if len(conflicts) >= MAX_CONTRADICTIONS:
                return conflicts
    return conflicts


def _hard_field_conflicts(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    source_map = {record["evidence_id"]: record for record in records}
    sources = [SourceText(document_id=row["evidence_id"], filename=row["safe_filename"], text=row["text"]) for row in records if row["text"]]
    output: list[dict[str, Any]] = []
    for conflict in find_cross_document_conflicts(sources):
        row = conflict.to_dict()
        for occurrence in row.get("occurrences") or []:
            source = source_map.get(str(occurrence.get("document_id") or ""), {})
            occurrence["source_hash"] = source.get("source_hash", "")
            occurrence["page_number"] = source.get("page_number", 0)
            occurrence["span_basis"] = source.get("span_basis", "indexed_text")
            occurrence.pop("filename", None)
            occurrence["safe_filename"] = source.get("safe_filename", "record")
        row["conflict_type"] = "hard_field_mismatch"
        row["does_not_prove"] = "Different values may concern different events or people. The mismatch requires source review."
        output.append(row)
    return output


def _exhibit_index(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        canonical = record["canonical_evidence_id"]
        current = grouped.get(canonical)
        row = {
            "exhibit_id": "",
            "canonical_evidence_id": canonical,
            "evidence_id": record["evidence_id"],
            "title": record["title"],
            "safe_filename": record["safe_filename"],
            "source_type": record["source_type"],
            "source_hash": record["source_hash"],
            "text_sha256": record["text_sha256"],
            "page_numbers": [record["page_number"]] if record["page_number"] else [],
            "duplicate_copy_count": record["duplicate_copy_count"],
            "parser_status": record["parser_status"],
            "ocr_status": record["ocr_status"],
            "ocr_derived": record["ocr_derived"],
            "privacy_status": record["privacy_status"],
            "review_required": True,
        }
        if current is None:
            grouped[canonical] = row
        else:
            current["page_numbers"] = sorted(set(current["page_numbers"] + row["page_numbers"]))
            current["duplicate_copy_count"] = max(current["duplicate_copy_count"], row["duplicate_copy_count"])
    rows = sorted(grouped.values(), key=lambda row: (row["safe_filename"].casefold(), row["canonical_evidence_id"]))
    for index, row in enumerate(rows, start=1):
        row["exhibit_id"] = f"exhibit-{index:03d}"
    return rows


def _missing_records(records: Sequence[dict[str, Any]], timeline: Sequence[dict[str, Any]], ledger: Sequence[dict[str, Any]], contradictions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = "\n".join(record["text"].casefold() for record in records)
    source_types = {record["source_type"].casefold() for record in records}
    filenames = {record["safe_filename"].casefold() for record in records}
    rows: list[dict[str, Any]] = []

    def add(code: str, reason: str, priority: str = "medium") -> None:
        rows.append({"code": code, "reason": reason, "priority": priority, "status": "missing_or_not_confirmed", "review_required": True})

    if ledger and not any("order" in source_type or "order" in name or "judgment" in name for source_type in source_types for name in filenames):
        add("operative_order_copy_not_confirmed", "Enforcement-related text was found, but an operative order or judgment document was not clearly identified.", "high")
    if ledger and not any(term in combined for term in ("served", "service", "notice")):
        add("notice_or_service_record_not_confirmed", "Notice or service information was not located in the selected indexed text.", "high")
    if not timeline:
        add("dated_event_records_not_confirmed", "No explicit dated event was extracted from the selected indexed text.")
    if contradictions:
        add("conflicting_record_values_require_resolution", f"{len(contradictions)} potential conflict or contradiction candidate(s) require source review.", "high")
    if any(not record["source_hash"] for record in records):
        add("source_hash_missing_for_one_or_more_records", "One or more indexed records lacked a valid source SHA-256.", "high")
    if any("required" in record["parser_status"].casefold() or "required" in record["ocr_status"].casefold() for record in records):
        add("unreadable_or_ocr_pending_records", "One or more selected records indicate additional parsing or OCR is required.", "high")
    if any(record["duplicate_copy_count"] > 1 for record in records):
        add("duplicate_copy_review", "Duplicate copies were grouped; confirm the canonical record and any material version differences.")
    if any(term in combined for term in ("child support", "arrears", "income")) and not any(term in " ".join(source_types | filenames) for term in ("financial", "worksheet", "paystub", "tax", "income")):
        add("financial_records_not_confirmed", "Support or income language appears, but financial records or worksheets were not clearly identified.")
    return sorted(rows, key=lambda row: ({"high": 0, "medium": 1, "low": 2}.get(row["priority"], 3), row["code"]))


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_count": len(packet["records"]),
        "timeline_event_count": len(packet["timeline"]),
        "enforcement_ledger_count": len(packet["contempt_enforcement_ledger"]),
        "contradiction_count": len(packet["contradictions"]),
        "exhibit_count": len(packet["exhibit_index"]),
        "missing_record_count": len(packet["missing_record_checklist"]),
        "review_required": True,
    }


def _render_html(packet: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    timeline = "".join(
        f"<article><h3>{esc(row['displayed_date'])} · {esc(row['date_type'].replace('_', ' '))}</h3>"
        f"<p>{esc(row['description'])}</p><small>{esc(row['source']['safe_filename'])} · {esc(row['source']['evidence_id'])} · span {row['source']['span_start']}–{row['source']['span_end']}</small></article>"
        for row in packet["timeline"][:1000]
    ) or "<p>No dated events were extracted.</p>"
    ledger = "".join(
        f"<article><h3>{esc(row['source']['safe_filename'])}</h3><p><strong>Order language:</strong> {len(row['operative_order_language'])} span(s) · <strong>Reported conduct:</strong> {len(row['alleged_or_reported_conduct'])} span(s)</p>"
        f"<p>{esc(', '.join(row['missing_elements']) or 'No automatic completeness finding.')}</p></article>"
        for row in packet["contempt_enforcement_ledger"][:500]
    ) or "<p>No enforcement-focused rows were extracted.</p>"
    conflicts = "".join(
        f"<article><h3>{esc(row.get('conflict_type'))}</h3><p>{esc(row.get('does_not_prove'))}</p><small>{esc(row.get('conflict_id'))}</small></article>"
        for row in packet["contradictions"][:500]
    ) or "<p>No deterministic conflict candidates were identified.</p>"
    missing = "".join(f"<li><strong>{esc(row['code'])}</strong> — {esc(row['reason'])}</li>" for row in packet["missing_record_checklist"]) or "<li>No automatic missing-record item was generated.</li>"
    exhibits = "".join(
        f"<tr><td>{esc(row['exhibit_id'])}</td><td>{esc(row['safe_filename'])}</td><td>{esc(row['source_type'])}</td><td>{esc(row['evidence_id'])}</td><td><code>{esc(row['source_hash'][:20])}</code></td></tr>"
        for row in packet["exhibit_index"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Maine Family Law LLM Evidence Work Product</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f5f1ea;color:#17212b}}main{{max-width:1100px;margin:auto;padding:28px}}section,article{{background:#fff;border:1px solid #d8d4ce;border-radius:12px;padding:16px;margin:12px 0}}article h3{{margin-top:0}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}code{{word-break:break-all}}.warning{{background:#fff4df;border-color:#d5a34b}}</style></head><body><main>
<h1>Evidence Work Product</h1><p><strong>Build:</strong> {esc(packet['build_id'])} · <strong>Generated:</strong> {esc(packet['generated_at'])}</p>
<section class="warning"><strong>Review required.</strong> This packet organizes indexed record text. It does not prove allegations, authenticity, credibility, intent, contempt, or legal entitlement.</section>
<section><h2>Summary</h2><pre>{esc(json.dumps(packet['summary'], indent=2, sort_keys=True))}</pre></section>
<section><h2>Timeline</h2>{timeline}</section>
<section><h2>Contempt and enforcement ledger</h2>{ledger}</section>
<section><h2>Contradictions and conflicts</h2>{conflicts}</section>
<section><h2>Missing-record checklist</h2><ul>{missing}</ul></section>
<section><h2>Exhibit index</h2><table><thead><tr><th>ID</th><th>File</th><th>Type</th><th>Evidence ID</th><th>Hash</th></tr></thead><tbody>{exhibits}</tbody></table></section>
</main></body></html>"""


class EvidenceWorkProductStore:
    def __init__(self, case_root: str | Path):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.is_dir():
            raise EvidenceWorkProductError("case_root_unavailable", "The active local matter is unavailable.", status_code=404)
        self.root = self.case_root / WORK_PRODUCT_FOLDER
        self.builds = self.root / "builds"
        self.active_pointer = self.root / "ACTIVE_BUILD.json"

    def _ensure_root(self) -> None:
        for path in (self.root, self.builds):
            if path.exists() and path.is_symlink():
                raise EvidenceWorkProductError("work_product_symlink_refused", "A symlinked work-product directory was refused.", status_code=409)
            path.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _contained(self, path: Path) -> Path:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self.root.resolve(strict=False))
        except ValueError as exc:
            raise EvidenceWorkProductError("work_product_path_escape", "A work-product path escaped the active matter.", status_code=409) from exc
        return resolved

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise EvidenceWorkProductError("work_product_record_unavailable", "The work-product record is unavailable.", status_code=404)
        raw = path.read_bytes()
        if len(raw) > MAX_JSON_BYTES:
            raise EvidenceWorkProductError("work_product_record_too_large", "The work-product record is unexpectedly large.", status_code=409)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceWorkProductError("work_product_record_invalid", "The work-product record is invalid.", status_code=409) from exc
        if not isinstance(payload, dict):
            raise EvidenceWorkProductError("work_product_record_invalid", "The work-product record is invalid.", status_code=409)
        return payload

    def build(
        self,
        records: Sequence[dict[str, Any]],
        *,
        selected_evidence_ids: Sequence[str] | None = None,
        focus_terms: Sequence[str] | None = None,
        activate: bool = True,
    ) -> EvidenceWorkProductResult:
        self._ensure_root()
        selected = {str(item).strip()[:256] for item in (selected_evidence_ids or []) if str(item).strip()}
        focus = []
        seen_focus: set[str] = set()
        for raw in focus_terms or []:
            term = " ".join(str(raw or "").replace("\x00", "").split())[:MAX_FOCUS_TERM_CHARS]
            if term and term.casefold() not in seen_focus:
                focus.append(term)
                seen_focus.add(term.casefold())
            if len(focus) >= MAX_FOCUS_TERMS:
                break
        safe_records, warnings = _record_rows(records, selected)
        if not safe_records:
            raise EvidenceWorkProductError("no_selected_indexed_records", "No matching indexed records were available for the work product.", status_code=404)

        fingerprint_input = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "selected_evidence_ids": sorted(selected),
            "focus_terms": sorted(focus, key=str.casefold),
            "records": [
                {
                    "evidence_id": row["evidence_id"],
                    "canonical_evidence_id": row["canonical_evidence_id"],
                    "source_hash": row["source_hash"],
                    "text_sha256": row["text_sha256"],
                    "page_number": row["page_number"],
                }
                for row in safe_records
            ],
        }
        fingerprint = _sha_bytes(_canonical_json(fingerprint_input))
        build_id = fingerprint[:24]
        build_root = self._contained(self.builds / build_id)
        packet_path = build_root / "evidence-work-product.json"
        receipt_path = build_root / "evidence-work-product-receipt.json"
        html_path = build_root / "evidence-work-product.html"

        if build_root.exists():
            verification = self.verify(build_id)
            if verification["status"] != "pass":
                raise EvidenceWorkProductError("immutable_work_product_collision", "An existing work-product build failed verification.", status_code=409)
            packet = self._read_json(packet_path)
            artifacts = self._artifacts(build_root)
            if activate:
                self._activate(build_id, receipt_path)
            return EvidenceWorkProductResult("pass", build_id, packet, artifacts, verification.get("blockers", []), warnings, True)

        timeline = _timeline(safe_records, focus)
        ledger = _contempt_ledger(safe_records, timeline)
        contradictions = (_hard_field_conflicts(safe_records) + _polarity_conflicts(safe_records))[:MAX_CONTRADICTIONS]
        packet: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "build_id": build_id,
            "build_fingerprint": fingerprint,
            "generated_at": _utc_now(),
            "scope": {
                "selected_evidence_ids": sorted(selected),
                "focus_terms": focus,
                "record_count": len(safe_records),
                "local_only": True,
            },
            "records": [
                {key: value for key, value in row.items() if key != "text"}
                for row in safe_records
            ],
            "timeline": timeline,
            "contempt_enforcement_ledger": ledger,
            "contradictions": contradictions,
            "exhibit_index": _exhibit_index(safe_records),
            "missing_record_checklist": [],
            "warnings": sorted(set(warnings)),
            "review_required": True,
            "export_status": "review_required",
            "legal_conclusion": "not_determined",
            "disclaimer": "This work product organizes indexed record text. It does not prove allegations, authenticity, credibility, intent, contempt, or legal entitlement.",
            "fingerprint_input": fingerprint_input,
        }
        packet["missing_record_checklist"] = _missing_records(safe_records, timeline, ledger, contradictions)
        packet["summary"] = _summary(packet)
        packet["packet_sha256"] = _sha_bytes(_canonical_json({key: value for key, value in packet.items() if key != "packet_sha256"}))

        staging = self._contained(self.builds / f".{build_id}.{secrets.token_hex(8)}.staging")
        try:
            staging.mkdir(parents=True, exist_ok=False, mode=0o700)
            self._atomic_json(staging / packet_path.name, packet)
            (staging / html_path.name).write_text(_render_html(packet), encoding="utf-8", newline="\n")
            os.chmod(staging / html_path.name, 0o600)
            artifacts_pre_receipt = [
                EvidenceArtifact("packet_json", packet_path.name, _sha_file(staging / packet_path.name), (staging / packet_path.name).stat().st_size, "application/json"),
                EvidenceArtifact("packet_html", html_path.name, _sha_file(staging / html_path.name), (staging / html_path.name).stat().st_size, "text/html"),
            ]
            receipt = {
                "schema_version": "evidence_work_product_receipt_v1",
                "build_id": build_id,
                "build_fingerprint": fingerprint,
                "packet_sha256": packet["packet_sha256"],
                "artifacts": [item.as_dict() for item in artifacts_pre_receipt],
                "source_manifest": fingerprint_input["records"],
                "generated_at": packet["generated_at"],
                "review_required": True,
            }
            receipt["receipt_sha256"] = _sha_bytes(_canonical_json({key: value for key, value in receipt.items() if key != "receipt_sha256"}))
            self._atomic_json(staging / receipt_path.name, receipt)
            try:
                os.replace(staging, build_root)
            except OSError:
                # A concurrent process may have promoted the identical content-addressed
                # build first. Reuse it only after independent verification below.
                if not build_root.exists():
                    raise
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

        verification = self.verify(build_id)
        if verification["status"] != "pass":
            raise EvidenceWorkProductError("work_product_verification_failed", "The generated work product failed independent verification.", status_code=409)
        if activate:
            self._activate(build_id, receipt_path)
        return EvidenceWorkProductResult("pass", build_id, packet, self._artifacts(build_root), verification.get("blockers", []), warnings)

    def _activate(self, build_id: str, receipt_path: Path) -> None:
        self._read_json(self.builds / build_id / receipt_path.name)
        pointer = {
            "schema_version": "active_evidence_work_product_v1",
            "build_id": build_id,
            "receipt_relative_path": f"builds/{build_id}/{receipt_path.name}",
            "receipt_sha256": _sha_file(self.builds / build_id / receipt_path.name),
            "activated_at": _utc_now(),
        }
        self._atomic_json(self.active_pointer, pointer)

    def _artifacts(self, build_root: Path) -> list[EvidenceArtifact]:
        rows = []
        for name, media_type in (
            ("evidence-work-product.json", "application/json"),
            ("evidence-work-product.html", "text/html"),
            ("evidence-work-product-receipt.json", "application/json"),
        ):
            path = build_root / name
            if path.is_file() and not path.is_symlink():
                rows.append(EvidenceArtifact(name.replace("-", "_").replace(".", "_"), f"builds/{build_root.name}/{name}", _sha_file(path), path.stat().st_size, media_type))
        return rows

    def verify(self, build_id: str | None = None) -> dict[str, Any]:
        self._ensure_root()
        blockers: list[str] = []
        if build_id is None:
            pointer = self._read_json(self.active_pointer)
            build_id = str(pointer.get("build_id") or "")
            receipt_rel = str(pointer.get("receipt_relative_path") or "")
            receipt_path = self._contained(self.root / receipt_rel)
            if not receipt_path.is_file() or receipt_path.is_symlink():
                blockers.append("active_receipt_unavailable")
            elif _sha_file(receipt_path) != str(pointer.get("receipt_sha256") or ""):
                blockers.append("active_receipt_hash_mismatch")
        if not re.fullmatch(r"[a-f0-9]{24}", str(build_id or "")):
            raise EvidenceWorkProductError("invalid_build_id", "The work-product build ID is invalid.", status_code=404)
        build_root = self._contained(self.builds / str(build_id))
        packet_path = build_root / "evidence-work-product.json"
        receipt_path = build_root / "evidence-work-product-receipt.json"
        html_path = build_root / "evidence-work-product.html"
        try:
            packet = self._read_json(packet_path)
            receipt = self._read_json(receipt_path)
        except EvidenceWorkProductError as exc:
            return {"status": "blocked", "build_id": build_id, "blockers": [exc.code], "review_required": True}
        fingerprint_input = packet.get("fingerprint_input")
        if not isinstance(fingerprint_input, dict):
            blockers.append("fingerprint_input_missing")
        else:
            fingerprint = _sha_bytes(_canonical_json(fingerprint_input))
            if fingerprint != str(packet.get("build_fingerprint") or "") or fingerprint[:24] != build_id:
                blockers.append("build_fingerprint_mismatch")
        packet_copy = dict(packet)
        stored_packet_hash = str(packet_copy.pop("packet_sha256", ""))
        if _sha_bytes(_canonical_json(packet_copy)) != stored_packet_hash:
            blockers.append("packet_content_hash_mismatch")
        receipt_copy = dict(receipt)
        stored_receipt_hash = str(receipt_copy.pop("receipt_sha256", ""))
        if _sha_bytes(_canonical_json(receipt_copy)) != stored_receipt_hash:
            blockers.append("receipt_content_hash_mismatch")
        if str(receipt.get("packet_sha256") or "") != stored_packet_hash:
            blockers.append("receipt_packet_hash_mismatch")
        for artifact in receipt.get("artifacts") or []:
            if not isinstance(artifact, dict):
                blockers.append("receipt_artifact_invalid")
                continue
            name = Path(str(artifact.get("relative_path") or "")).name
            path = self._contained(build_root / name)
            if not path.is_file() or path.is_symlink():
                blockers.append(f"artifact_unavailable:{name}")
                continue
            if _sha_file(path) != str(artifact.get("sha256") or ""):
                blockers.append(f"artifact_hash_mismatch:{name}")
            if path.stat().st_size != int(artifact.get("size_bytes") or -1):
                blockers.append(f"artifact_size_mismatch:{name}")
        if not html_path.is_file() or html_path.is_symlink():
            blockers.append("packet_html_unavailable")
        return {
            "status": "pass" if not blockers else "blocked",
            "build_id": build_id,
            "blockers": sorted(set(blockers)),
            "packet_sha256": stored_packet_hash,
            "receipt_sha256": stored_receipt_hash,
            "review_required": True,
        }

    def active(self) -> dict[str, Any]:
        verification = self.verify(None)
        if verification["status"] != "pass":
            return verification
        build_id = verification["build_id"]
        packet = self._read_json(self.builds / build_id / "evidence-work-product.json")
        return {
            "status": "pass",
            "build_id": build_id,
            "packet": packet,
            "artifacts": [item.as_dict() for item in self._artifacts(self.builds / build_id)],
            "verification": verification,
            "review_required": True,
        }

    def resolve_artifact(self, build_id: str, filename: str) -> tuple[Path, str]:
        if not re.fullmatch(r"[a-f0-9]{24}", str(build_id or "")):
            raise EvidenceWorkProductError("invalid_build_id", "The work-product build ID is invalid.", status_code=404)
        allowed = {
            "evidence-work-product.json": "application/json",
            "evidence-work-product.html": "text/html",
            "evidence-work-product-receipt.json": "application/json",
        }
        safe_name = Path(str(filename or "")).name
        if safe_name not in allowed:
            raise EvidenceWorkProductError("artifact_not_allowed", "The requested work-product artifact is not allowed.", status_code=404)
        verification = self.verify(build_id)
        if verification["status"] != "pass":
            raise EvidenceWorkProductError("artifact_build_unverified", "The work-product build failed verification.", status_code=409)
        path = self._contained(self.builds / build_id / safe_name)
        if not path.is_file() or path.is_symlink():
            raise EvidenceWorkProductError("artifact_unavailable", "The requested work-product artifact is unavailable.", status_code=404)
        return path, allowed[safe_name]
