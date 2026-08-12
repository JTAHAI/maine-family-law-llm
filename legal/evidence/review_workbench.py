from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, UTC
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from legal.documents.docx_engine import create_docx_from_text

_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(r"\bbetween\s+(.+?)\s+and\s+(.+?)\b", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[^\n.!?]+(?:[.!?]+|$)", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NEGATION_MARKERS = (" not ", " no ", " never ", " failed ", " refused ", " unpaid ", " denied ", " without ")
_ALLEGATION_MARKERS = (" alleges ", " alleged ", " claims ", " states ", " reported ", " says ")
_OBSERVATION_MARKERS = (" observed ", " saw ", " received ", " attached ", " shows ", " notes ", " records ")
_FINDING_MARKERS = (" the court finds ", " found ", " ordered ", " it is ordered ", " judgment ", " decree ", " order entered ")
_QUALIFICATION_MARKERS = (" however ", " but ", " except ", " unless ", " to the extent ", " according to ")
_ALTERNATIVE_MARKERS = (" because ", " due to ", " since ", " after ", " while ", " during ")
_DATE_TYPES = (
    "alleged event date",
    "message timestamp",
    "document-created date",
    "filing date",
    "service date",
    "hearing date",
    "order date",
    "payment date",
    "medical/school record date",
    "unknown/other",
)
_SUPPORTED_EXPORT_FORMATS = {"json", "md", "txt", "docx"}
_SUPPORTED_EXPORT_KINDS = {
    "chronology",
    "claim-evidence",
    "contradiction",
    "missing-record-checklist",
    "enforcement-ledger",
    "review-handoff",
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(data: str | bytes | dict[str, Any] | list[Any]) -> str:
    if isinstance(data, bytes):
        raw = data
    elif isinstance(data, (dict, list)):
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    else:
        raw = str(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_text(value: Any, *, limit: int = 2000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _safe_id(prefix: str, *parts: Any) -> str:
    payload = "\0".join(_safe_text(part, limit=1000) for part in parts)
    return f"{prefix}-{_sha(payload)[:16]}"


def _tokenize(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(value.casefold()) if len(token) > 1}


def _normalize_date(value: str) -> str:
    raw = value.strip().replace("Sept.", "Sep.")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw.casefold()


def _parse_date_value(value: str | None) -> str | None:
    raw = _safe_text(value, limit=80)
    if not raw:
        return None
    if _DATE_RE.fullmatch(raw):
        return _normalize_date(raw)
    return None


def _as_date(value: str | None) -> date | None:
    parsed = _parse_date_value(value)
    if not parsed:
        return None
    try:
        return date.fromisoformat(parsed)
    except ValueError:
        return None


def _sentence_rows(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _SENTENCE_RE.finditer(text):
        sentence = " ".join(match.group(0).split())
        if sentence:
            yield sentence, match.start(), match.end()


def _sentence_context(text: str, start: int, end: int, radius: int = 120) -> str:
    return " ".join(text[max(0, start - radius) : min(len(text), end + radius)].split())


def _source_display(value: Any) -> str:
    text = _safe_text(value, limit=400)
    if "!" in text:
        text = text.rsplit("!", 1)[-1]
    if "#page=" in text:
        text = text.split("#page=", 1)[0] + text[text.index("#page="):]
    return Path(text.replace("\\", "/")).name or text[:120]


def _record_text(row: dict[str, Any]) -> str:
    for key in ("text", "derived_text", "content", "text_excerpt", "snippet"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return _safe_text(value, limit=500_000)
    return ""


def _date_type(sentence: str, source_type: str, fallback: str = "unknown/other") -> str:
    lowered = f" {_safe_text(sentence).casefold()} "
    if any(term in lowered for term in (" hearing ", " hearing.", " trial ", " conference ", " mediation ")):
        return "hearing date"
    if any(term in lowered for term in (" served ", " service ", " notice ", " summons ")):
        return "service date"
    if any(term in lowered for term in (" file ", " filed ", " filing ", " submitted to court ")):
        return "filing date"
    if any(term in lowered for term in (" order ", " judgment ", " decree ", " entered ")):
        return "order date"
    if any(term in lowered for term in (" paid ", " payment ", " support ", " arrears ")):
        return "payment date"
    if any(term in lowered for term in (" school ", " medical ", " doctor ", " therapist ", " clinic ")):
        return "medical/school record date"
    if source_type in {"email", "text", "sms", "message"}:
        return "message timestamp"
    return fallback


def _assertion_classification(sentence: str, source_type: str) -> str:
    lowered = f" {_safe_text(sentence).casefold()} "
    if any(marker in lowered for marker in _FINDING_MARKERS):
        return "found"
    if any(marker in lowered for marker in _OBSERVATION_MARKERS) or source_type in {"email", "text", "sms", "message"}:
        return "observed"
    if any(marker in lowered for marker in _ALLEGATION_MARKERS):
        return "alleged"
    return "observed" if source_type in {"medical", "school"} else "alleged"


def _confidence_basis(sentence: str, date_count: int, source_hash: str) -> str:
    bits = ["deterministic_rule"]
    if date_count:
        bits.append("explicit_date_match")
    if source_hash:
        bits.append("source_hash_bound")
    if any(marker in f" {_safe_text(sentence).casefold()} " for marker in _FINDING_MARKERS):
        bits.append("court_finding_language")
    return ",".join(bits)


def _event_signature(event: dict[str, Any]) -> str:
    return _sha({
        "event_label": event.get("event_label"),
        "date_value": event.get("date_value"),
        "source_record_id": event.get("source_record_id"),
        "source_block": event.get("source_block"),
        "date_type": event.get("date_type"),
    })


def _claim_signature(claim: dict[str, Any]) -> str:
    return _sha({
        "statement": claim.get("statement"),
        "claim_type": claim.get("claim_type"),
        "scope": claim.get("scope"),
    })


def _history_entry(*, action: str, entity_type: str, entity_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None, summary: str) -> dict[str, Any]:
    return {
        "history_id": _safe_id("hist", action, entity_type, entity_id, time.time_ns()),
        "generated_at": _utc_now(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_sha256": _sha(before or {}),
        "after_sha256": _sha(after or {}),
        "summary": summary[:1000],
        "review_required": True,
    }


@dataclass(frozen=True)
class EvidenceReviewResult:
    status: str
    matter_id: str
    payload: dict[str, Any]
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "matter_id": self.matter_id,
            "payload": self.payload,
            "review_required": self.review_required,
        }


class EvidenceReviewStore:
    def __init__(self, case_root: Path):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.is_dir():
            raise ValueError("case_root_unavailable")
        self.root = self.case_root / "19_EVIDENCE_WORK_PRODUCT" / "review-workbench"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "evidence-review-state.json"
        self.history_path = self.root / "evidence-review-history.jsonl"
        self._lock = threading.Lock()

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": "evidence_review_workbench_v1",
            "matter_id": self.case_root.name,
            "timeline": {
                "build_id": "",
                "fingerprint": "",
                "generated_at": "",
                "status": "empty",
                "selected_record_ids": [],
                "filters": {},
                "events": [],
                "conflicts": [],
                "duplicate_groups": [],
                "near_duplicate_candidates": [],
                "records_by_date": {},
                "events_by_date": {},
                "undated_records": [],
                "empty_date_ranges": [],
                "date_span": {"earliest": None, "latest": None},
                "coverage": {},
            },
            "claims": {},
            "claims_history": {},
            "missing_records": {},
            "ledger": {},
            "ledger_history": {},
            "review_history": [],
            "exports": {},
            "last_updated_at": _utc_now(),
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_state()
        if not isinstance(payload, dict):
            return self._default_state()
        return payload

    def _save_state(self, state: dict[str, Any]) -> None:
        state["last_updated_at"] = _utc_now()
        temporary = self.state_path.parent / f".{self.state_path.name}.{secrets.token_hex(8)}.tmp"
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n")
        temporary.replace(self.state_path)

    def _append_history_log(self, entry: dict[str, Any]) -> None:
        with self.history_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
            handle.write("\n")

    def _record_history(self, state: dict[str, Any], entry: dict[str, Any]) -> None:
        state.setdefault("review_history", []).append(entry)
        self._append_history_log(entry)

    def _records(self, records: Iterable[dict[str, Any]], selected_record_ids: Iterable[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        rows = []
        warnings: list[str] = []
        selected = {str(item).strip() for item in (selected_record_ids or []) if str(item).strip()}
        for raw in records:
            if not isinstance(raw, dict):
                continue
            evidence_id = _safe_text(raw.get("evidence_id") or raw.get("source_id") or "", limit=120)
            if not evidence_id:
                continue
            if selected and evidence_id not in selected and str(raw.get("parent_evidence_id") or "") not in selected:
                continue
            text = _record_text(raw)
            if not text:
                warnings.append(f"record_text_missing:{evidence_id}")
            rows.append({
                "evidence_id": evidence_id,
                "title": _safe_text(raw.get("title") or raw.get("subject") or evidence_id, limit=300),
                "source_type": _safe_text(raw.get("source_type") or raw.get("document_type") or "record", limit=80),
                "source_hash": _safe_text(raw.get("source_hash") or raw.get("sha256") or "", limit=64).lower(),
                "text": text[:500_000],
                "text_sha256": _sha(text),
                "page_number": max(0, int(raw.get("page_number") or 0)),
                "span_start": int(raw.get("span_start") or 0) if raw.get("span_start") is not None else None,
                "span_end": int(raw.get("span_end") or 0) if raw.get("span_end") is not None else None,
                "block_id": _safe_text(raw.get("block_id"), limit=120),
                "parser_status": _safe_text(raw.get("parser_status"), limit=80),
                "ocr_status": _safe_text(raw.get("ocr_status"), limit=80),
                "issue_tags": list(raw.get("issue_lanes") or raw.get("issue_tags") or []) if isinstance(raw.get("issue_lanes") or raw.get("issue_tags"), list) else [],
                "duplicate_group": _safe_text(raw.get("canonical_evidence_id") or raw.get("canonical_document_key") or raw.get("evidence_id") or "", limit=120),
                "source_locator": _source_display(raw.get("source_locator") or raw.get("source_path") or raw.get("filename") or raw.get("title") or evidence_id),
                "records_found": [],
            })
        return rows, warnings

    def _extract_events_from_record(self, record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        text = record["text"]
        events: list[dict[str, Any]] = []
        undated: list[dict[str, Any]] = []
        for sentence, start, end in _sentence_rows(text):
            dates = list(_DATE_RE.finditer(sentence))
            if not dates:
                if any(term in f" {sentence.casefold()} " for term in (" hearing ", " order ", " notice ", " service ", " filed ", " paid ", " school ", " medical ")):
                    undated.append({
                        "event_label": sentence[:240],
                        "source_record_id": record["evidence_id"],
                        "source_block": {"block_id": record.get("block_id") or None, "page_number": record["page_number"], "span_start": start, "span_end": end},
                        "date_value": "unknown",
                    })
                continue
            for match in dates:
                event = {
                    "event_id": _safe_id("event", record["evidence_id"], sentence, match.group(0), start, end),
                    "event_label": sentence[:240],
                    "classification": _assertion_classification(sentence, record["source_type"]),
                    "date_value": _normalize_date(match.group(0)),
                    "date_range": {"start": _normalize_date(match.group(0)), "end": _normalize_date(match.group(0))},
                    "date_precision": "day",
                    "date_type": _date_type(sentence, record["source_type"]),
                    "source_record_id": record["evidence_id"],
                    "source_block": {
                        "block_id": record.get("block_id") or None,
                        "page_number": record["page_number"],
                        "span_start": start,
                        "span_end": end,
                        "context": _sentence_context(text, start, end),
                    },
                    "source_hash": record["source_hash"],
                    "actor_refs": [],
                    "participant_refs": [],
                    "issue_tags": list(record.get("issue_tags") or []),
                    "confidence_basis": _confidence_basis(sentence, len(dates), record["source_hash"]),
                    "extraction_method": "deterministic_rule",
                    "reviewer_status": "review_required",
                    "conflicts": [],
                    "duplicate_group": record.get("duplicate_group") or record["source_hash"] or record["evidence_id"],
                    "correction_history": [],
                    "notes": "Record presence is not proof.",
                    "child_impact_tags": [],
                    "review_required": True,
                }
                events.append(event)
        return events, undated

    def build_timeline(
        self,
        records: Iterable[dict[str, Any]],
        *,
        selected_record_ids: Iterable[str] | None = None,
        issue_tags: Iterable[str] | None = None,
        source_types: Iterable[str] | None = None,
        allegation_observation_finding: Iterable[str] | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        cancel_requested: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            rows, warnings = self._records(records, selected_record_ids)
            selected = {str(item).strip() for item in (selected_record_ids or []) if str(item).strip()}
            source_type_filter = {str(item).strip().casefold() for item in (source_types or []) if str(item).strip()}
            issue_filter = {str(item).strip().casefold() for item in (issue_tags or []) if str(item).strip()}
            assertion_filter = {str(item).strip().casefold() for item in (allegation_observation_finding or []) if str(item).strip()}
            start_date = _as_date(date_start)
            end_date = _as_date(date_end)
            extracted: list[dict[str, Any]] = []
            undated_records: list[dict[str, Any]] = []
            records_by_date: dict[str, list[str]] = {}
            events_by_date: dict[str, list[str]] = {}
            duplicate_groups: dict[str, list[str]] = {}
            near_duplicate_candidates: list[dict[str, Any]] = []
            parser_ocr_failures: list[dict[str, Any]] = []
            selected_records = []
            for record in rows:
                if cancel_requested:
                    warnings.append("timeline_build_cancelled")
                    break
                if source_type_filter and record["source_type"].casefold() not in source_type_filter:
                    continue
                if issue_filter and not (issue_filter & {tag.casefold() for tag in record.get("issue_tags") or []}):
                    continue
                selected_records.append(record)
                duplicate_groups.setdefault(record["duplicate_group"] or record["source_hash"] or record["evidence_id"], []).append(record["evidence_id"])
                if record["parser_status"] and any(marker in record["parser_status"].casefold() for marker in ("fail", "error", "blocked", "required")):
                    parser_ocr_failures.append({"record_id": record["evidence_id"], "status": record["parser_status"], "kind": "parser"})
                if record["ocr_status"] and any(marker in record["ocr_status"].casefold() for marker in ("fail", "error", "blocked", "required")):
                    parser_ocr_failures.append({"record_id": record["evidence_id"], "status": record["ocr_status"], "kind": "ocr"})
                events, undated = self._extract_events_from_record(record)
                for event in events:
                    if assertion_filter and event["classification"] not in assertion_filter and event["date_type"] not in assertion_filter:
                        continue
                    event_date = _as_date(event["date_value"])
                    if start_date and event_date and event_date < start_date:
                        continue
                    if end_date and event_date and event_date > end_date:
                        continue
                    extracted.append(event)
                    records_by_date.setdefault(event["date_value"], []).append(record["evidence_id"])
                    events_by_date.setdefault(event["date_value"], []).append(event["event_id"])
                undated_records.extend([
                    {
                        **item,
                        "issue_tags": list(record.get("issue_tags") or []),
                        "source_type": record["source_type"],
                        "source_hash": record["source_hash"],
                        "review_required": True,
                    }
                    for item in undated
                ])

            exact_duplicate_groups = [
                {
                    "duplicate_group": group,
                    "record_ids": ids,
                    "duplicate_count": len(ids),
                }
                for group, ids in duplicate_groups.items()
                if len(ids) > 1
            ]

            for left_index, left in enumerate(extracted):
                for right in extracted[left_index + 1 :]:
                    if left["source_record_id"] == right["source_record_id"]:
                        continue
                    if left["date_value"] == right["date_value"]:
                        continue
                    shared_terms = _tokenize(left["event_label"]) & _tokenize(right["event_label"])
                    if len(shared_terms) < 3:
                        continue
                    left.setdefault("conflicts", []).append(right["event_id"])
                    right.setdefault("conflicts", []).append(left["event_id"])

            dates = sorted({event["date_value"] for event in extracted if _as_date(event["date_value"])})
            empty_ranges: list[dict[str, Any]] = []
            if len(dates) >= 2:
                prev = _as_date(dates[0])
                for current in dates[1:]:
                    dt = _as_date(current)
                    if prev and dt and (dt - prev).days > 1:
                        empty_ranges.append({
                            "start": (prev + timedelta(days=1)).isoformat(),
                            "end": (dt - timedelta(days=1)).isoformat(),
                            "days_missing": (dt - prev).days - 1,
                            "review_required": True,
                            "does_not_prove": "An empty date range does not prove nothing happened; it only shows no selected record was dated in that interval.",
                        })
                    prev = dt

            if extracted:
                earliest = min((d for d in (_as_date(item["date_value"]) for item in extracted) if d), default=None)
                latest = max((d for d in (_as_date(item["date_value"]) for item in extracted) if d), default=None)
            else:
                earliest = latest = None

            for record in rows:
                text = record["text"]
                for other in rows:
                    if other["evidence_id"] <= record["evidence_id"]:
                        continue
                    score = SequenceMatcher(None, text[:4000], other["text"][:4000]).ratio() if text or other["text"] else 0.0
                    if score >= 0.86 and record["source_hash"] != other["source_hash"]:
                        near_duplicate_candidates.append({
                            "left_record_id": record["evidence_id"],
                            "right_record_id": other["evidence_id"],
                            "similarity": round(score, 6),
                            "same_duplicate_group": record["duplicate_group"] == other["duplicate_group"],
                            "review_required": True,
                        })
                if len(near_duplicate_candidates) >= 200:
                    break

            build_material = {
                "matter_id": state.get("matter_id") or self.case_root.name,
                "selected_record_ids": sorted(selected),
                "issue_tags": sorted(issue_filter),
                "source_types": sorted(source_type_filter),
                "assertion_filter": sorted(assertion_filter),
                "records": [record["evidence_id"] for record in selected_records],
            }
            fingerprint = _sha(build_material)
            build_id = fingerprint[:24]
            timeline = {
                "build_id": build_id,
                "fingerprint": fingerprint,
                "generated_at": _utc_now(),
                "status": "cancelled" if cancel_requested else "pass",
                "selected_record_ids": sorted(selected),
                "filters": {
                    "issue_tags": sorted(issue_filter),
                    "source_types": sorted(source_type_filter),
                    "assertion_filter": sorted(assertion_filter),
                    "date_start": date_start,
                    "date_end": date_end,
                },
                "events": extracted,
                "conflicts": [
                    {
                        "conflict_id": _safe_id("conflict", item.get("event_id"), item.get("conflicts")),
                        "conflict_type": "conflicting_dates",
                        "event_id": item.get("event_id"),
                        "conflicting_event_ids": sorted(set(item.get("conflicts") or [])),
                        "review_required": True,
                        "does_not_prove": "Conflicting dates remain visible and require source review.",
                    }
                    for item in extracted
                    if item.get("conflicts")
                ],
                "duplicate_groups": exact_duplicate_groups,
                "near_duplicate_candidates": near_duplicate_candidates[:200],
                "records_by_date": records_by_date,
                "events_by_date": events_by_date,
                "undated_records": undated_records,
                "empty_date_ranges": empty_ranges,
                "date_span": {"earliest": earliest.isoformat() if earliest else None, "latest": latest.isoformat() if latest else None},
                "coverage": {
                    "total_records_considered": len(rows),
                    "selected_records": len(selected_records),
                    "records_with_dated_events": len(records_by_date),
                    "records_without_explicit_dates": len(undated_records),
                    "duplicate_group_count": len(exact_duplicate_groups),
                    "near_duplicate_candidate_count": len(near_duplicate_candidates),
                    "parser_ocr_failure_count": len(parser_ocr_failures),
                },
                "parser_ocr_failures": parser_ocr_failures,
            }
            state["timeline"] = timeline
            self._record_history(state, _history_entry(action="build_timeline", entity_type="timeline", entity_id=build_id, before=None, after=timeline, summary=f"Built timeline from {len(selected_records)} selected record(s)."))
            self._save_state(state)
            return {
                "schema_version": "evidence_timeline_response_v1",
                "matter_id": state.get("matter_id") or self.case_root.name,
                "timeline": timeline,
                "coverage": timeline["coverage"],
                "selected_record_ids": sorted(selected),
                "undated_records": undated_records,
                "review_history": state.get("review_history", [])[-100:],
                "warnings": sorted(set(warnings)),
                "status": timeline["status"],
                "review_required": True,
            }

    def get_timeline(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            events = list(timeline.get("events") or [])
            start = max(0, int(offset or 0))
            end = start + max(0, int(limit or 0))
            return {
                "schema_version": "evidence_timeline_response_v1",
                "matter_id": state.get("matter_id") or self.case_root.name,
                "timeline": {**timeline, "events": events[start:end]},
                "coverage": timeline.get("coverage", {}),
                "total_events": len(events),
                "offset": start,
                "limit": max(0, int(limit or 0)),
                "review_history": state.get("review_history", [])[-100:],
                "review_required": True,
            }

    def create_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            event = {
                "event_id": _safe_id("event", time.time_ns(), payload.get("event_label"), payload.get("source_record_id")),
                "event_label": _safe_text(payload.get("event_label") or payload.get("label") or "Untitled event", limit=240),
                "classification": _safe_text(payload.get("classification") or "observed", limit=40),
                "date_value": _safe_text(payload.get("date_value") or payload.get("date") or "unknown", limit=40),
                "date_range": payload.get("date_range") or {"start": payload.get("date_value") or payload.get("date"), "end": payload.get("date_value") or payload.get("date")},
                "date_precision": _safe_text(payload.get("date_precision") or "unknown", limit=40),
                "date_type": _safe_text(payload.get("date_type") or "unknown/other", limit=40),
                "source_record_id": _safe_text(payload.get("source_record_id") or "", limit=120),
                "source_block": payload.get("source_block") or {},
                "source_hash": _safe_text(payload.get("source_hash") or "", limit=64),
                "actor_refs": list(payload.get("actor_refs") or []),
                "participant_refs": list(payload.get("participant_refs") or []),
                "issue_tags": list(payload.get("issue_tags") or []),
                "confidence_basis": _safe_text(payload.get("confidence_basis") or "review_required", limit=200),
                "extraction_method": _safe_text(payload.get("extraction_method") or "manual", limit=80),
                "reviewer_status": _safe_text(payload.get("reviewer_status") or "review_required", limit=80),
                "conflicts": list(payload.get("conflicts") or []),
                "duplicate_group": _safe_text(payload.get("duplicate_group") or "", limit=120),
                "correction_history": [],
                "notes": _safe_text(payload.get("notes") or "", limit=1000),
                "child_impact_tags": list(payload.get("child_impact_tags") or []),
                "review_required": True,
            }
            timeline.setdefault("events", []).append(event)
            state["timeline"] = timeline
            state.setdefault("review_history", []).append(_history_entry(action="create", entity_type="event", entity_id=event["event_id"], before=None, after=event, summary=f"Manual event added: {event['event_label']}"))
            self._append_history_log(state["review_history"][-1])
            self._save_state(state)
            return {"status": "pass", "event": event, "review_required": True}

    def patch_event(self, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            events = list(timeline.get("events") or [])
            for index, event in enumerate(events):
                if str(event.get("event_id") or "") != str(event_id or ""):
                    continue
                before = dict(event)
                correction = {
                    "corrected_at": _utc_now(),
                    "previous": {k: before.get(k) for k in ("date_value", "date_range", "date_precision", "date_type", "event_label", "classification")},
                    "updated_by": _safe_text(payload.get("reviewer_name") or payload.get("reviewer") or "reviewer", limit=120),
                    "reason": _safe_text(payload.get("reason") or payload.get("notes") or "", limit=500),
                }
                event["correction_history"] = list(event.get("correction_history") or []) + [correction]
                for key in ("event_label", "classification", "date_value", "date_range", "date_precision", "date_type", "notes", "issue_tags", "actor_refs", "participant_refs", "child_impact_tags", "reviewer_status"):
                    if key in payload:
                        event[key] = payload[key]
                event["review_required"] = True
                events[index] = event
                timeline["events"] = events
                state["timeline"] = timeline
                history = _history_entry(action="patch", entity_type="event", entity_id=event_id, before=before, after=event, summary="Event corrected with append-only history.")
                state.setdefault("review_history", []).append(history)
                self._append_history_log(history)
                self._save_state(state)
                return {"status": "pass", "event": event, "history": event["correction_history"], "review_required": True}
            raise KeyError("event_not_found")

    def get_event_history(self, event_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            history = [row for row in state.get("review_history", []) if row.get("entity_type") == "event" and row.get("entity_id") == event_id]
            return {"status": "pass", "event_id": event_id, "history": history, "review_required": True}

    def create_claim(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            selected_records, _warnings = self._records(records, payload.get("selected_record_ids") or [])
            statement = _safe_text(payload.get("statement") or payload.get("claim") or "", limit=2000)
            claim = {
                "claim_id": _safe_id("claim", time.time_ns(), statement, payload.get("scope")),
                "statement": statement,
                "claim_type": _safe_text(payload.get("claim_type") or "factual_claim", limit=80),
                "scope": _safe_text(payload.get("scope") or "selected_records", limit=120),
                "source_of_claim": _safe_text(payload.get("source_of_claim") or payload.get("origin") or "user", limit=80),
                "supporting_spans": [],
                "contradicting_spans": [],
                "qualifying_spans": [],
                "alternative_explanations": [],
                "missing_context": [],
                "unresolved_questions": [],
                "reviewer_status": "review_required",
                "history": [],
                "selected_record_ids": [record["evidence_id"] for record in selected_records],
                "selected_sentence": _safe_text(payload.get("selected_sentence") or "", limit=1000),
                "promoted_from_record_id": _safe_text(payload.get("promoted_from_record_id") or "", limit=120),
                "date_range": payload.get("date_range") or {},
                "issue_tags": list(payload.get("issue_tags") or []),
                "child_impact_tags": list(payload.get("child_impact_tags") or []),
                "review_required": True,
            }
            evaluation = self._evaluate_claim(statement, selected_records, claim)
            claim.update(evaluation)
            claim["history"].append(_history_entry(action="create", entity_type="claim", entity_id=claim["claim_id"], before=None, after=claim, summary="Claim created and reviewed against selected records."))
            state.setdefault("claims", {})[claim["claim_id"]] = claim
            state.setdefault("claims_history", {})[claim["claim_id"]] = list(claim["history"])
            history = _history_entry(action="create", entity_type="claim", entity_id=claim["claim_id"], before=None, after=claim, summary="Claim saved with evidence cards.")
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "claim": claim, "review_required": True}

    def _evaluate_claim(self, statement: str, records: list[dict[str, Any]], claim: dict[str, Any]) -> dict[str, Any]:
        claim_tokens = _tokenize(statement)
        support_cards: list[dict[str, Any]] = []
        contradict_cards: list[dict[str, Any]] = []
        qualify_cards: list[dict[str, Any]] = []
        alternative_cards: list[dict[str, Any]] = []
        missing_cards: list[dict[str, Any]] = []
        outside_cards: list[dict[str, Any]] = []
        caveat_cards: list[dict[str, Any]] = []
        unresolved_cards: list[dict[str, Any]] = []
        for record in records:
            text = record["text"]
            source_tokens = _tokenize(text)
            overlap = len(claim_tokens & source_tokens)
            if not overlap:
                continue
            for sentence, start, end in _sentence_rows(text):
                sent_tokens = _tokenize(sentence)
                match_overlap = len(claim_tokens & sent_tokens)
                if match_overlap == 0:
                    continue
                context = _sentence_context(text, start, end)
                card_base = {
                    "record_id": record["evidence_id"],
                    "record_classification": _assertion_classification(sentence, record["source_type"]),
                    "source_hash": record["source_hash"],
                    "date_context": {
                        "date_value": next(( _normalize_date(match.group(0)) for match in _DATE_RE.finditer(sentence) ), "unknown"),
                        "date_type": _date_type(sentence, record["source_type"]),
                    },
                    "source_span": {"page_number": record["page_number"], "span_start": start, "span_end": end},
                    "exact_source_span": sentence[:2000],
                    "context_window": context,
                    "match_explanation": f"{match_overlap} token(s) overlap with the claim statement.",
                    "confidence_basis": "deterministic_rule",
                    "review_required": True,
                }
                lowered = f" {sentence.casefold()} "
                if any(marker in lowered for marker in _NEGATION_MARKERS):
                    contradict_cards.append({**card_base, "relationship": "contradicts"})
                elif any(marker in lowered for marker in _QUALIFICATION_MARKERS) or "only" in lowered or "limited to" in lowered:
                    qualify_cards.append({**card_base, "relationship": "qualifies"})
                elif any(marker in lowered for marker in _ALTERNATIVE_MARKERS):
                    alternative_cards.append({**card_base, "relationship": "alternative_explanation"})
                else:
                    support_cards.append({**card_base, "relationship": "supports"})
                if record.get("parser_status") or record.get("ocr_status"):
                    caveat_cards.append({
                        **card_base,
                        "relationship": "authenticity_reliability_caveat",
                        "match_explanation": "Parser/OCR status suggests this source may need extra review.",
                        "source_status": {"parser_status": record.get("parser_status"), "ocr_status": record.get("ocr_status")},
                    })
                if record.get("duplicate_group"):
                    unresolved_cards.append({**card_base, "relationship": "unresolved", "match_explanation": "A duplicate group exists; compare copies before relying on wording."})
        if not support_cards and not contradict_cards and not qualify_cards:
            missing_cards.append({
                "relationship": "missing_context",
                "match_explanation": "No selected record sentence directly matched the claim text.",
                "review_required": True,
            })
        return {
            "supports": support_cards[:100],
            "contradicts": contradict_cards[:100],
            "qualifies": qualify_cards[:100],
            "alternative_explanations": alternative_cards[:100],
            "missing_context": missing_cards[:100],
            "outside_scope": outside_cards[:100],
            "authenticity_reliability_caveat": caveat_cards[:100],
            "unresolved": unresolved_cards[:100],
            "claim_history": claim.get("history", []),
        }

    def review_claim(self, claim_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            claim = dict(state.get("claims", {}).get(claim_id) or {})
            if not claim:
                raise KeyError("claim_not_found")
            before = dict(claim)
            claim["reviewer_status"] = _safe_text(payload.get("reviewer_status") or payload.get("decision") or "review_required", limit=80)
            claim["reviewer_notes"] = _safe_text(payload.get("reviewer_notes") or payload.get("notes") or "", limit=2000)
            claim["history"] = list(claim.get("history") or []) + [{
                "reviewed_at": _utc_now(),
                "reviewer_status": claim["reviewer_status"],
                "reviewer_notes": claim["reviewer_notes"],
            }]
            state.setdefault("claims", {})[claim_id] = claim
            state.setdefault("claims_history", {})[claim_id] = list(claim["history"])
            history = _history_entry(action="review", entity_type="claim", entity_id=claim_id, before=before, after=claim, summary="Claim reviewer decision recorded.")
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "claim": claim, "review_required": True}

    def get_claim(self, claim_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            claim = dict(state.get("claims", {}).get(claim_id) or {})
            if not claim:
                raise KeyError("claim_not_found")
            return {"status": "pass", "claim": claim, "history": list(state.get("claims_history", {}).get(claim_id) or []), "review_required": True}

    def coverage(self, *, records: Iterable[dict[str, Any]], selected_record_ids: Iterable[str] | None = None) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            rows, warnings = self._records(records, selected_record_ids)
            selected = {str(item).strip() for item in (selected_record_ids or []) if str(item).strip()}
            selected_rows = rows if not selected else [row for row in rows if row["evidence_id"] in selected or row["duplicate_group"] in selected]
            selected_ids = {row["evidence_id"] for row in selected_rows}
            all_ids = {row["evidence_id"] for row in rows}
            excluded = sorted(all_ids - selected_ids)
            dated_records = []
            undated_records = []
            source_type_counts: dict[str, int] = {}
            for row in selected_rows:
                source_type_counts[row["source_type"]] = source_type_counts.get(row["source_type"], 0) + 1
                if _DATE_RE.search(row["text"]):
                    dated_records.append(row["evidence_id"])
                else:
                    undated_records.append(row["evidence_id"])
            return {
                "schema_version": "evidence_coverage_response_v1",
                "matter_id": state.get("matter_id") or self.case_root.name,
                "records_total": len(rows),
                "searchable_records": len(selected_rows),
                "selected_record_ids": sorted(selected_ids),
                "excluded_records": excluded,
                "records_by_date": timeline.get("records_by_date", {}),
                "events_by_date": timeline.get("events_by_date", {}),
                "empty_date_ranges": timeline.get("empty_date_ranges", []),
                "date_span": timeline.get("date_span", {}),
                "undated_records": undated_records,
                "record_types_represented": sorted(source_type_counts),
                "source_type_counts": source_type_counts,
                "duplicate_concentration": timeline.get("duplicate_groups", []),
                "near_duplicate_candidates": timeline.get("near_duplicate_candidates", []),
                "parser_ocr_failures": timeline.get("parser_ocr_failures", []),
                "coverage_notes": [
                    "An empty date range does not prove nothing happened.",
                    "Coverage reflects selected indexed records only.",
                ],
                "warnings": sorted(set(warnings)),
                "review_history": state.get("review_history", [])[-100:],
                "review_required": True,
            }

    def create_missing_records(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            items = []
            template_id = _safe_text(payload.get("template_id") or "", limit=80)
            for raw in payload.get("items") or []:
                if not isinstance(raw, dict):
                    continue
                item_id = raw.get("item_id") or _safe_id("miss", time.time_ns(), raw.get("expected_record_description"))
                item = {
                    "item_id": item_id,
                    "origin_type": _safe_text(raw.get("origin_type") or "user", limit=40),
                    "expected_record_description": _safe_text(raw.get("expected_record_description") or "", limit=400),
                    "relevant_date_range": raw.get("relevant_date_range") or {},
                    "why_it_may_matter": _safe_text(raw.get("why_it_may_matter") or "", limit=600),
                    "basis_for_expectation": _safe_text(raw.get("basis_for_expectation") or template_id or "user checklist", limit=600),
                    "search_performed": _safe_text(raw.get("search_performed") or "", limit=600),
                    "records_found": list(raw.get("records_found") or []),
                    "status": _safe_text(raw.get("status") or "review_required", limit=80),
                    "reviewer_decision": _safe_text(raw.get("reviewer_decision") or "", limit=120),
                    "review_required": True,
                }
                items.append(item)
                state.setdefault("missing_records", {})[item["item_id"]] = item
            if not items and template_id:
                heuristic = self._heuristic_missing_items(payload, records)
                items.extend(heuristic)
                for item in heuristic:
                    state.setdefault("missing_records", {})[item["item_id"]] = item
            history = _history_entry(action="create", entity_type="missing_record", entity_id=template_id or "missing_record_items", before=None, after={"items": items}, summary="Missing-record checklist updated.")
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "missing_records": items, "review_required": True}

    def _heuristic_missing_items(self, payload: dict[str, Any], records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rows, _warnings = self._records(records, payload.get("selected_record_ids") or [])
        source_types = {row["source_type"].casefold() for row in rows}
        combined = " ".join(row["text"].casefold() for row in rows)
        items: list[dict[str, Any]] = []
        def add(description: str, basis: str, reason: str) -> None:
            items.append({
                "item_id": _safe_id("miss", description, basis, reason),
                "origin_type": "heuristic",
                "expected_record_description": description,
                "relevant_date_range": payload.get("relevant_date_range") or {},
                "why_it_may_matter": reason,
                "basis_for_expectation": basis,
                "search_performed": "Selected indexed records reviewed for matching and related terms.",
                "records_found": [],
                "status": "review_required",
                "reviewer_decision": "",
                "review_required": True,
            })
        if "order" not in source_types and any(term in combined for term in ("enforce", "contempt", "noncompliance", "arrears")):
            add("Operative order or judgment", "heuristic_enforcement_review", "Enforcement-related language appears, so the current order text may matter.")
        if "served" not in combined and any(term in combined for term in ("notice", "motion", "request")):
            add("Service or notice record", "heuristic_notice_review", "Notice/service may matter to review the selected dispute.")
        if any(term in combined for term in ("hearing", "conference", "trial")) and not any(term in source_types for term in ("transcript", "audio", "minutes")):
            add("Hearing notice or transcript", "heuristic_hearing_review", "A hearing reference appears but no matching hearing record was identified.")
        if any(term in combined for term in ("school", "medical", "doctor", "therap", "counsel")) and not any(term in source_types for term in ("school", "medical", "healthcare", "therapy")):
            add("Referenced school or medical records", "user_or_template_review_aid", "The user selected a topic that may need corroborating records.")
        return items[:50]

    def get_missing_records(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            return {"status": "pass", "missing_records": list((state.get("missing_records") or {}).values()), "review_required": True}

    def get_ledger(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            return {"status": "pass", "ledger": list((state.get("ledger") or {}).values()), "review_required": True}

    def create_ledger_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            exact_order_language = _safe_text(payload.get("exact_order_term") or payload.get("operative_order_language") or "", limit=1000)
            if not exact_order_language:
                raise ValueError("operative_order_language_required")
            event = {
                "event_id": _safe_id("ledger", time.time_ns(), exact_order_language, payload.get("event_date")),
                "event_date": _safe_text(payload.get("event_date") or "unknown", limit=40),
                "operative_order_record": _safe_text(payload.get("operative_order_record") or "", limit=120),
                "exact_order_term": exact_order_language,
                "required_conduct": _safe_text(payload.get("required_conduct") or "", limit=600),
                "alleged_or_observed_conduct": _safe_text(payload.get("alleged_or_observed_conduct") or "", limit=600),
                "supporting_spans": list(payload.get("supporting_spans") or []),
                "contradicting_spans": list(payload.get("contradicting_spans") or []),
                "notice_service_status": _safe_text(payload.get("notice_service_status") or "unknown", limit=80),
                "ability_to_comply_information": _safe_text(payload.get("ability_to_comply_information") or "unknown", limit=120),
                "requested_relief": _safe_text(payload.get("requested_relief") or "", limit=200),
                "missing_evidence": list(payload.get("missing_evidence") or []),
                "unresolved_facts": list(payload.get("unresolved_facts") or []),
                "reviewer_status": _safe_text(payload.get("reviewer_status") or "review_required", limit=80),
                "stale_order_warning": bool(payload.get("stale_order_warning")),
                "review_required": True,
                "does_not_prove": "This ledger organizes alleged or observed conduct against exact order language and does not decide contempt, willfulness, or ability to comply.",
            }
            if any(term in exact_order_language.casefold() for term in ("superseded", "vacated", "amended", "replaced")):
                event["stale_order_warning"] = True
            state.setdefault("ledger", {})[event["event_id"]] = event
            history = _history_entry(action="create", entity_type="ledger_event", entity_id=event["event_id"], before=None, after=event, summary="Enforcement ledger event created.")
            state.setdefault("ledger_history", {}).setdefault(event["event_id"], []).append(history)
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "event": event, "review_required": True}

    def patch_ledger_event(self, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            ledger = dict(state.get("ledger") or {})
            event = dict(ledger.get(event_id) or {})
            if not event:
                raise KeyError("ledger_event_not_found")
            before = dict(event)
            if "exact_order_term" in payload or "operative_order_language" in payload:
                exact_order_language = _safe_text(payload.get("exact_order_term") or payload.get("operative_order_language") or "", limit=1000)
                if not exact_order_language:
                    raise ValueError("operative_order_language_required")
                event["exact_order_term"] = exact_order_language
            for key in ("event_date", "operative_order_record", "required_conduct", "alleged_or_observed_conduct", "notice_service_status", "ability_to_comply_information", "requested_relief", "reviewer_status"):
                if key in payload:
                    event[key] = _safe_text(payload.get(key), limit=1000)
            for key in ("supporting_spans", "contradicting_spans", "missing_evidence", "unresolved_facts"):
                if key in payload:
                    event[key] = list(payload.get(key) or [])
            event["stale_order_warning"] = bool(payload.get("stale_order_warning", event.get("stale_order_warning")))
            event["review_required"] = True
            ledger[event_id] = event
            state["ledger"] = ledger
            history = _history_entry(action="patch", entity_type="ledger_event", entity_id=event_id, before=before, after=event, summary="Ledger event corrected with append-only history.")
            state.setdefault("ledger_history", {}).setdefault(event_id, []).append(history)
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "event": event, "history": list(state.get("ledger_history", {}).get(event_id) or []), "review_required": True}

    def export_work_product(
        self,
        *,
        export_kind: str,
        format_name: str,
        selected_record_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if export_kind not in _SUPPORTED_EXPORT_KINDS:
                raise ValueError("unsupported_export_kind")
            format_name = format_name.lower().strip()
            if format_name not in _SUPPORTED_EXPORT_FORMATS:
                raise ValueError("unsupported_export_format")
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            records, _warnings = self._records(selected_record_ids or [], selected_record_ids)
            export_dir = self.root / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            export_payload = {
                "review_required": True,
                "matter_id": state.get("matter_id") or self.case_root.name,
                "export_kind": export_kind,
                "format": format_name,
                "generated_at": _utc_now(),
                "selected_record_ids": list(selected_record_ids or []),
                "timeline_build_id": timeline.get("build_id"),
                "unresolved_items": {
                    "claims": [claim_id for claim_id, claim in (state.get("claims") or {}).items() if str(claim.get("reviewer_status") or "review_required") != "resolved"],
                    "missing_records": list((state.get("missing_records") or {}).keys()),
                },
                "correction_history_summary": {
                    "timeline_events": sum(len(event.get("correction_history") or []) for event in timeline.get("events") or []),
                    "claims": sum(len(claim.get("history") or []) for claim in (state.get("claims") or {}).values()),
                    "ledger": sum(len(rows) for rows in (state.get("ledger_history") or {}).values()),
                },
                "source_ids": sorted(timeline.get("selected_record_ids") or []),
                "source_hashes": [],
            }
            export_text = self._render_export_text(export_kind, state, export_payload)
            body_hash = _sha(export_text)
            safe_name = f"{export_kind}-{body_hash[:24]}"
            if format_name == "json":
                path = export_dir / f"{safe_name}.json"
                path.write_text(json.dumps({**export_payload, "payload": export_text}, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n")
                media_type = "application/json"
            elif format_name == "md":
                path = export_dir / f"{safe_name}.md"
                path.write_text(export_text, encoding="utf-8", newline="\n")
                media_type = "text/markdown"
            elif format_name == "txt":
                path = export_dir / f"{safe_name}.txt"
                path.write_text(export_text, encoding="utf-8", newline="\n")
                media_type = "text/plain"
            else:
                path = export_dir / f"{safe_name}.docx"
                create_docx_from_text(title=f"Evidence {export_kind.replace('-', ' ').title()}", content=export_text, output_path=path, allowed_output_root=export_dir)
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            receipt = {
                "schema_version": "evidence_review_export_receipt_v1",
                "export_kind": export_kind,
                "format": format_name,
                "generated_at": _utc_now(),
                "matter_id": state.get("matter_id") or self.case_root.name,
                "selected_record_ids": list(selected_record_ids or []),
                "source_ids": export_payload["source_ids"],
                "source_hashes": export_payload["source_hashes"],
                "unresolved_items": export_payload["unresolved_items"],
                "correction_history_summary": export_payload["correction_history_summary"],
                "review_required": True,
                "artifact_sha256": _sha(path.read_bytes() if path.exists() else export_text),
                "artifact_relative_path": path.relative_to(self.case_root).as_posix(),
            }
            receipt["receipt_sha256"] = _sha(receipt)
            receipt_path = export_dir / f"{safe_name}-receipt.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n")
            export_row = {
                "export_id": safe_name,
                "export_kind": export_kind,
                "format": format_name,
                "artifact_relative_path": path.relative_to(self.case_root).as_posix(),
                "artifact_sha256": receipt["artifact_sha256"],
                "receipt_relative_path": receipt_path.relative_to(self.case_root).as_posix(),
                "receipt_sha256": receipt["receipt_sha256"],
                "media_type": media_type,
                "generated_at": receipt["generated_at"],
                "review_required": True,
            }
            state.setdefault("exports", {})[safe_name] = export_row
            history = _history_entry(action="export", entity_type="export", entity_id=safe_name, before=None, after=export_row, summary=f"Evidence export generated in {format_name} format.")
            state.setdefault("review_history", []).append(history)
            self._append_history_log(history)
            self._save_state(state)
            return {"status": "pass", "artifact": export_row, "receipt": receipt, "review_required": True}

    def _render_export_text(self, export_kind: str, state: dict[str, Any], export_payload: dict[str, Any]) -> str:
        timeline = dict(state.get("timeline") or self._default_state()["timeline"])
        claims = list((state.get("claims") or {}).values())
        missing_records = list((state.get("missing_records") or {}).values())
        ledger = list((state.get("ledger") or {}).values())
        lines = [
            "REVIEW REQUIRED",
            f"Matter: {export_payload['matter_id']}",
            f"Export kind: {export_kind}",
            f"Generated at: {export_payload['generated_at']}",
            f"Selected record IDs: {', '.join(export_payload['selected_record_ids']) or 'all available selected records'}",
            "",
        ]
        if export_kind == "chronology":
            lines.append("Timeline")
            for event in timeline.get("events") or []:
                lines.append(f"- {event.get('event_id')} | {event.get('date_value')} | {event.get('event_label')} | {event.get('source_record_id')}")
        elif export_kind == "claim-evidence":
            lines.append("Claims")
            for claim in claims:
                lines.append(f"- {claim.get('claim_id')} | {claim.get('statement')} | status: {claim.get('reviewer_status')}")
        elif export_kind == "contradiction":
            lines.append("Contradiction review")
            for event in timeline.get("conflicts") or []:
                lines.append(f"- {event.get('conflict_id')} | {event.get('does_not_prove')}")
        elif export_kind == "missing-record-checklist":
            lines.append("Missing records")
            for item in missing_records:
                lines.append(f"- {item.get('item_id')} | {item.get('expected_record_description')} | origin: {item.get('origin_type')}")
        elif export_kind == "enforcement-ledger":
            lines.append("Enforcement ledger")
            for row in ledger:
                lines.append(f"- {row.get('event_id')} | {row.get('event_date')} | {row.get('exact_order_term')}")
        else:
            lines.append("Review handoff")
            lines.append("The handoff should be interpreted as review-required analytical work product, not legal authority.")
        lines.append("")
        lines.append("Unresolved items")
        lines.append(json.dumps(export_payload["unresolved_items"], indent=2, sort_keys=True))
        lines.append("")
        lines.append("Correction history summary")
        lines.append(json.dumps(export_payload["correction_history_summary"], indent=2, sort_keys=True))
        return "\n".join(lines).strip() + "\n"

    def get_review_history(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            rows = list(state.get("review_history") or [])
            start = max(0, int(offset or 0))
            end = start + max(0, int(limit or 0))
            return {
                "status": "pass",
                "matter_id": state.get("matter_id") or self.case_root.name,
                "history": rows[start:end],
                "total": len(rows),
                "offset": start,
                "limit": max(0, int(limit or 0)),
                "review_required": True,
            }
