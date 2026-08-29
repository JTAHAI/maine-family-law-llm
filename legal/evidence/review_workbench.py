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
_CLAIM_REVIEW_STATUSES = {
    "review_required",
    "accepted_with_qualification",
    "needs_more_context",
    "needs_revision",
    "unsupported",
    "contradicted",
    "not_material",
}
_CLAIM_CARD_KINDS = {
    "supports",
    "contradicts",
    "qualifies",
    "alternative_explanations",
    "authenticity_reliability_caveat",
    "unresolved",
}
_ATTACHMENT_COVERAGE_STATES = {
    "alleged",
    "referenced",
    "expected",
    "absent_in_selected_scope",
    "not_yet_reviewed",
    "located",
}
_FACT_GRAPH_NODE_KINDS = {"person", "event", "order", "assertion", "record", "source"}
_FACT_GRAPH_STATES = {"unknown", "disputed", "observed", "alleged", "not_yet_reviewed"}
_FACT_GRAPH_RELATIONSHIPS = {
    "mentions", "supports", "contradicts", "qualifies", "relates_to", "describes", "supersedes",
    "temporal_before", "temporal_after", "attachment_of", "reply_to", "duplicate_of", "derivative_of",
}
_ISSUE_PROOF_EVIDENCE_ROLES = {"supports", "contradicts", "qualifies", "missing_proof"}
_ISSUE_PROOF_REVIEW_STATES = {"not_yet_reviewed", "review_required", "reviewed_with_qualification"}
_RECORD_LINEAGE_RELATIONSHIPS = {"exact_duplicate", "changed_copy", "ocr_correction", "translation", "redaction", "export_derivative", "derived_copy"}
_ENTITY_RESOLUTION_TYPES = {"person", "organization", "location", "other"}
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
            "attachment_coverage": {},
            "attachment_coverage_history": {},
            "fact_graph": {"nodes": {}, "edges": {}},
            "fact_graph_history": [],
            "issue_proof_matrix": {},
            "issue_proof_matrix_history": {},
            "change_digest_checkpoints": {},
            "change_digest_history": {},
            "record_lineage": {},
            "record_lineage_history": {},
            "entity_resolution": {},
            "entity_resolution_history": {},
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

    def _event_source_binding(
        self,
        payload: dict[str, Any],
        records: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """Bind a manual timeline event to an inventory record, never caller-supplied provenance."""
        source_record_id = _safe_text(payload.get("source_record_id") or "", limit=120)
        requested_hash = _safe_text(payload.get("source_hash") or "", limit=64).lower()
        if not source_record_id:
            if requested_hash:
                raise ValueError("source_rebind_record_required")
            return {
                "source_record_id": "",
                "source_hash": "",
                "source_block": {},
                "source_binding_status": "unbound_review_required",
            }

        rows, _warnings = self._records(records)
        source = next(
            (row for row in rows if row["evidence_id"] == source_record_id),
            None,
        )
        if source is None:
            raise ValueError("source_record_not_found_in_active_matter")
        actual_hash = str(source.get("source_hash") or "").lower()
        if requested_hash and requested_hash != actual_hash:
            raise ValueError("source_rebind_hash_mismatch")
        if not actual_hash:
            raise ValueError("source_rebind_hash_unavailable")
        return {
            "source_record_id": source["evidence_id"],
            "source_hash": actual_hash,
            "source_block": {
                "record_id": source["evidence_id"],
                "block_id": source.get("block_id") or "",
                "page_number": source.get("page_number") or 0,
                "span_start": source.get("span_start"),
                "span_end": source.get("span_end"),
            },
            "source_binding_status": "bound_to_active_matter_record",
        }

    def create_event(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]] = ()
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            source_binding = self._event_source_binding(payload, records)
            event = {
                "event_id": _safe_id("event", time.time_ns(), payload.get("event_label"), source_binding["source_record_id"]),
                "event_label": _safe_text(payload.get("event_label") or payload.get("label") or "Untitled event", limit=240),
                "classification": _safe_text(payload.get("classification") or "observed", limit=40),
                "date_value": _safe_text(payload.get("date_value") or payload.get("date") or "unknown", limit=40),
                "date_range": payload.get("date_range") or {"start": payload.get("date_value") or payload.get("date"), "end": payload.get("date_value") or payload.get("date")},
                "date_precision": _safe_text(payload.get("date_precision") or "unknown", limit=40),
                "date_type": _safe_text(payload.get("date_type") or "unknown/other", limit=40),
                **source_binding,
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

    def patch_event(
        self, event_id: str, payload: dict[str, Any], *, records: Iterable[dict[str, Any]] = ()
    ) -> dict[str, Any]:
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
                    "previous": {k: before.get(k) for k in ("date_value", "date_range", "date_precision", "date_type", "event_label", "classification", "source_record_id", "source_hash", "source_block", "source_binding_status")},
                    "updated_by": _safe_text(payload.get("reviewer_name") or payload.get("reviewer") or "reviewer", limit=120),
                    "reason": _safe_text(payload.get("reason") or payload.get("notes") or "", limit=500),
                }
                event["correction_history"] = list(event.get("correction_history") or []) + [correction]
                for key in ("event_label", "classification", "date_value", "date_range", "date_precision", "date_type", "notes", "issue_tags", "actor_refs", "participant_refs", "child_impact_tags", "reviewer_status"):
                    if key in payload:
                        event[key] = payload[key]
                if "source_record_id" in payload or "source_hash" in payload:
                    event.update(self._event_source_binding(payload, records))
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
            timeline = dict(state.get("timeline") or self._default_state()["timeline"])
            event = next(
                (row for row in timeline.get("events", []) if str(row.get("event_id") or "") == str(event_id or "")),
                None,
            )
            if event is None:
                raise KeyError("event_not_found")
            history = [row for row in state.get("review_history", []) if row.get("entity_type") == "event" and row.get("entity_id") == event_id]
            return {
                "status": "pass",
                "event_id": event_id,
                "event": event,
                "history": history,
                "source_drill_down_available": bool(event.get("source_record_id") and event.get("source_hash")),
                "review_required": True,
            }

    def create_claim(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            selected_ids = [str(item).strip() for item in (payload.get("selected_record_ids") or []) if str(item).strip()]
            if not selected_ids:
                raise ValueError("claim_source_record_required")
            selected_records, _warnings = self._records(records, selected_ids)
            selected_ids_found = {str(record.get("evidence_id") or "") for record in selected_records}
            if any(item not in selected_ids_found for item in selected_ids):
                raise ValueError("claim_source_record_not_found_in_active_matter")
            statement = _safe_text(payload.get("statement") or payload.get("claim") or "", limit=2000)
            if not statement:
                raise ValueError("claim_statement_required")
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
                # Normalize punctuation so a review signal such as "However,"
                # is not silently missed merely because it starts a sentence.
                lowered = f" {re.sub(r'[^a-z0-9]+', ' ', sentence.casefold())} "
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
        if contradict_cards:
            automated_disposition = "contradicted_or_disputed_review_required"
        elif support_cards and (qualify_cards or alternative_cards or caveat_cards or unresolved_cards):
            automated_disposition = "support_with_qualifications_review_required"
        elif support_cards:
            automated_disposition = "candidate_support_review_required"
        else:
            automated_disposition = "no_candidate_support_in_selected_records"
        disposition_blockers = []
        if contradict_cards:
            disposition_blockers.append("contradicting_source_cards_present")
        if qualify_cards or alternative_cards:
            disposition_blockers.append("qualifying_or_alternative_context_present")
        if caveat_cards:
            disposition_blockers.append("source_reliability_review_required")
        if unresolved_cards:
            disposition_blockers.append("duplicate_or_unresolved_source_review_required")
        if missing_cards:
            disposition_blockers.append("selected_records_do_not_directly_match_claim")
        return {
            "supports": support_cards[:100],
            "contradicts": contradict_cards[:100],
            "qualifies": qualify_cards[:100],
            "alternative_explanations": alternative_cards[:100],
            "missing_context": missing_cards[:100],
            "outside_scope": outside_cards[:100],
            "authenticity_reliability_caveat": caveat_cards[:100],
            "unresolved": unresolved_cards[:100],
            "automated_disposition": automated_disposition,
            "disposition_blockers": disposition_blockers,
            "automated_disposition_notice": "This deterministic review aid does not determine whether a claim is true, legally sufficient, or filing ready.",
            "claim_history": claim.get("history", []),
        }

    def review_claim(self, claim_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            claim = dict(state.get("claims", {}).get(claim_id) or {})
            if not claim:
                raise KeyError("claim_not_found")
            before = dict(claim)
            reviewer_status = _safe_text(payload.get("reviewer_status") or payload.get("decision") or "review_required", limit=80)
            if reviewer_status not in _CLAIM_REVIEW_STATUSES:
                raise ValueError("claim_reviewer_status_invalid")
            claim["reviewer_status"] = reviewer_status
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

    def get_claim_source_card(self, claim_id: str, card_kind: str, card_index: int) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            claim = dict(state.get("claims", {}).get(claim_id) or {})
            if not claim:
                raise KeyError("claim_not_found")
            if card_kind not in _CLAIM_CARD_KINDS:
                raise ValueError("claim_source_card_kind_invalid")
            cards = list(claim.get(card_kind) or [])
            if card_index < 0 or card_index >= len(cards):
                raise KeyError("claim_source_card_not_found")
            card = dict(cards[card_index] or {})
            record_id = _safe_text(card.get("record_id") or "", limit=120)
            source_hash = _safe_text(card.get("source_hash") or "", limit=64).lower()
            if not record_id or not source_hash:
                raise ValueError("claim_source_card_unbound")
            return {
                "status": "pass",
                "claim_id": claim_id,
                "card_kind": card_kind,
                "card_index": card_index,
                "card": card,
                "record_id": record_id,
                "source_hash": source_hash,
                "review_required": True,
            }

    def _attachment_binding(
        self,
        source_record_id: str,
        source_hash: str,
        records: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._event_source_binding(
            {"source_record_id": source_record_id, "source_hash": source_hash}, records
        )

    def create_attachment_coverage(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            attachment_id = _safe_text(payload.get("attachment_id") or "", limit=120)
            attachment_label = _safe_text(payload.get("attachment_label") or payload.get("label") or "", limit=300)
            coverage_state = _safe_text(payload.get("coverage_state") or "referenced", limit=80)
            if not attachment_id or not attachment_label:
                raise ValueError("attachment_id_and_label_required")
            if coverage_state not in _ATTACHMENT_COVERAGE_STATES:
                raise ValueError("attachment_coverage_state_invalid")
            coverage = dict(state.get("attachment_coverage") or {})
            if attachment_id in coverage:
                raise ValueError("attachment_coverage_id_exists")
            binding = self._attachment_binding(
                _safe_text(payload.get("source_record_id") or "", limit=120),
                _safe_text(payload.get("source_hash") or "", limit=64),
                records,
            )
            if not binding.get("source_record_id"):
                raise ValueError("attachment_source_record_required")
            linked_record_id = _safe_text(payload.get("linked_record_id") or "", limit=120)
            if linked_record_id:
                linked = self._attachment_binding(linked_record_id, "", records)
                if not linked.get("source_record_id"):
                    raise ValueError("attachment_linked_record_required")
            item = {
                "attachment_id": attachment_id,
                "attachment_label": attachment_label,
                "coverage_state": coverage_state,
                "coverage_scope": "selected_active_matter_records_only",
                **binding,
                "linked_record_id": linked_record_id,
                "reviewer_status": "review_required",
                "reviewer_notes": "",
                "history": [],
                "review_required": True,
            }
            entry = _history_entry(
                action="create",
                entity_type="attachment_coverage",
                entity_id=attachment_id,
                before=None,
                after=item,
                summary="Attachment coverage item recorded without inferring completeness.",
            )
            item["history"] = [entry]
            coverage[attachment_id] = item
            state["attachment_coverage"] = coverage
            state.setdefault("attachment_coverage_history", {})[attachment_id] = list(item["history"])
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "attachment": item, "review_required": True}

    def review_attachment_coverage(
        self, attachment_id: str, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            coverage = dict(state.get("attachment_coverage") or {})
            item = dict(coverage.get(attachment_id) or {})
            if not item:
                raise KeyError("attachment_coverage_not_found")
            before = dict(item)
            coverage_state = _safe_text(payload.get("coverage_state") or item.get("coverage_state") or "not_yet_reviewed", limit=80)
            if coverage_state not in _ATTACHMENT_COVERAGE_STATES:
                raise ValueError("attachment_coverage_state_invalid")
            linked_record_id = _safe_text(payload.get("linked_record_id") or item.get("linked_record_id") or "", limit=120)
            if coverage_state == "located" and not linked_record_id:
                raise ValueError("located_attachment_record_required")
            if linked_record_id:
                self._attachment_binding(linked_record_id, "", records)
            item["coverage_state"] = coverage_state
            item["linked_record_id"] = linked_record_id
            item["reviewer_status"] = "review_required"
            item["reviewer_notes"] = _safe_text(payload.get("reviewer_notes") or payload.get("notes") or "", limit=2000)
            entry = _history_entry(
                action="review",
                entity_type="attachment_coverage",
                entity_id=attachment_id,
                before=before,
                after=item,
                summary="Attachment coverage state reviewed; no completeness or legal conclusion inferred.",
            )
            item["history"] = list(item.get("history") or []) + [entry]
            coverage[attachment_id] = item
            state["attachment_coverage"] = coverage
            state.setdefault("attachment_coverage_history", {})[attachment_id] = list(item["history"])
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "attachment": item, "review_required": True}

    def attachment_coverage(self, attachment_id: str = "") -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            coverage = dict(state.get("attachment_coverage") or {})
            if attachment_id:
                item = dict(coverage.get(attachment_id) or {})
                if not item:
                    raise KeyError("attachment_coverage_not_found")
                return {
                    "status": "pass",
                    "attachment": item,
                    "history": list(state.get("attachment_coverage_history", {}).get(attachment_id) or []),
                    "review_required": True,
                }
            rows = sorted(coverage.values(), key=lambda row: str(row.get("attachment_id") or ""))
            states = {name: 0 for name in sorted(_ATTACHMENT_COVERAGE_STATES)}
            for row in rows:
                value = str(row.get("coverage_state") or "not_yet_reviewed")
                states[value] = states.get(value, 0) + 1
            return {
                "status": "pass",
                "attachments": rows,
                "state_counts": states,
                "notice": "An absent-in-scope item is not a finding that an attachment does not exist elsewhere.",
                "review_required": True,
            }

    def _fact_graph_source_binding(
        self, payload: dict[str, Any], records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        binding = self._event_source_binding(
            {"source_record_id": payload.get("source_record_id"), "source_hash": payload.get("source_hash")}, records
        )
        if not binding.get("source_record_id"):
            raise ValueError("fact_graph_source_record_required")
        return binding

    def create_fact_graph_node(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            graph = dict(state.get("fact_graph") or {})
            nodes = dict(graph.get("nodes") or {})
            node_id = _safe_text(payload.get("node_id") or "", limit=120)
            node_kind = _safe_text(payload.get("node_kind") or "", limit=40)
            label = _safe_text(payload.get("label") or "", limit=300)
            fact_state = _safe_text(payload.get("fact_state") or "not_yet_reviewed", limit=80)
            if not node_id or not label:
                raise ValueError("fact_graph_node_id_and_label_required")
            if node_id in nodes:
                raise ValueError("fact_graph_node_id_exists")
            if node_kind not in _FACT_GRAPH_NODE_KINDS:
                raise ValueError("fact_graph_node_kind_invalid")
            if fact_state not in _FACT_GRAPH_STATES:
                raise ValueError("fact_graph_state_invalid")
            node = {
                "node_id": node_id,
                "node_kind": node_kind,
                "label": label,
                "fact_state": fact_state,
                **self._fact_graph_source_binding(payload, records),
                "reviewer_status": "review_required",
                "review_required": True,
            }
            entry = _history_entry(action="create", entity_type="fact_graph_node", entity_id=node_id, before=None, after=node, summary="Source-bound fact graph node recorded without inferring a finding.")
            nodes[node_id] = node
            graph["nodes"] = nodes
            graph.setdefault("edges", {})
            state["fact_graph"] = graph
            state.setdefault("fact_graph_history", []).append(entry)
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "node": node, "review_required": True}

    def create_fact_graph_edge(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            graph = dict(state.get("fact_graph") or {})
            nodes = dict(graph.get("nodes") or {})
            edges = dict(graph.get("edges") or {})
            edge_id = _safe_text(payload.get("edge_id") or "", limit=120)
            source_node_id = _safe_text(payload.get("source_node_id") or "", limit=120)
            target_node_id = _safe_text(payload.get("target_node_id") or "", limit=120)
            relationship = _safe_text(payload.get("relationship") or "", limit=80)
            fact_state = _safe_text(payload.get("fact_state") or "not_yet_reviewed", limit=80)
            if not edge_id or not source_node_id or not target_node_id:
                raise ValueError("fact_graph_edge_ids_required")
            if edge_id in edges:
                raise ValueError("fact_graph_edge_id_exists")
            if source_node_id not in nodes or target_node_id not in nodes:
                raise ValueError("fact_graph_edge_node_not_found")
            if relationship not in _FACT_GRAPH_RELATIONSHIPS:
                raise ValueError("fact_graph_relationship_invalid")
            if fact_state not in _FACT_GRAPH_STATES:
                raise ValueError("fact_graph_state_invalid")
            edge = {
                "edge_id": edge_id,
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "relationship": relationship,
                "fact_state": fact_state,
                **self._fact_graph_source_binding(payload, records),
                "relationship_basis": _safe_text(payload.get("relationship_basis") or "reviewer_supplied", limit=120),
                "relationship_note": _safe_text(payload.get("relationship_note") or "", limit=2_000),
                "reviewer_status": "review_required",
                "review_required": True,
            }
            entry = _history_entry(action="create", entity_type="fact_graph_edge", entity_id=edge_id, before=None, after=edge, summary="Source-bound graph relationship recorded without inferring a finding.")
            edges[edge_id] = edge
            graph["nodes"] = nodes
            graph["edges"] = edges
            state["fact_graph"] = graph
            state.setdefault("fact_graph_history", []).append(entry)
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "edge": edge, "review_required": True}

    def fact_graph(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            graph = dict(state.get("fact_graph") or {})
            nodes = sorted(dict(graph.get("nodes") or {}).values(), key=lambda row: str(row.get("node_id") or ""))
            edges = sorted(dict(graph.get("edges") or {}).values(), key=lambda row: str(row.get("edge_id") or ""))
            state_counts = {name: 0 for name in sorted(_FACT_GRAPH_STATES)}
            for row in [*nodes, *edges]:
                value = str(row.get("fact_state") or "not_yet_reviewed")
                state_counts[value] = state_counts.get(value, 0) + 1
            return {
                "status": "pass",
                "nodes": nodes,
                "edges": edges,
                "state_counts": state_counts,
                "history": list(state.get("fact_graph_history") or [])[-100:],
                "notice": "Graph relationships are source-bound review records, not findings, legal conclusions, or a resolution of disputed facts.",
                "review_required": True,
            }

    def fact_graph_source(self, entity_kind: str, entity_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            graph = dict(state.get("fact_graph") or {})
            collection = dict(graph.get("nodes" if entity_kind == "nodes" else "edges") or {})
            row = dict(collection.get(entity_id) or {})
            if not row:
                raise KeyError("fact_graph_entity_not_found")
            return {"status": "pass", "entity": row, "review_required": True}

    def create_issue_proof_item(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        """Record a review-only issue/proof row anchored to an active-matter record.

        An authority string is deliberately preserved only as an unverified candidate.
        This workbench is not an authority resolver and cannot turn a matrix row into
        an element determination, a factual finding, or filing approval.
        """
        with self._lock:
            state = self._load_state()
            items = dict(state.get("issue_proof_matrix") or {})
            item_id = _safe_text(payload.get("item_id") or "", limit=120)
            issue_id = _safe_text(payload.get("issue_id") or "", limit=120)
            issue_label = _safe_text(payload.get("issue_label") or "", limit=300)
            proof_item_id = _safe_text(payload.get("proof_item_id") or "", limit=120)
            proof_label = _safe_text(payload.get("proof_label") or "", limit=500)
            evidence_role = _safe_text(payload.get("evidence_role") or "", limit=80)
            review_state = _safe_text(payload.get("review_state") or "review_required", limit=80)
            if not all((item_id, issue_id, issue_label, proof_item_id, proof_label)):
                raise ValueError("issue_proof_required_fields_missing")
            if item_id in items:
                raise ValueError("issue_proof_item_id_exists")
            if evidence_role not in _ISSUE_PROOF_EVIDENCE_ROLES:
                raise ValueError("issue_proof_evidence_role_invalid")
            if review_state not in _ISSUE_PROOF_REVIEW_STATES:
                raise ValueError("issue_proof_review_state_invalid")
            binding = self._event_source_binding(
                {
                    "source_record_id": payload.get("source_record_id"),
                    "source_hash": payload.get("source_hash"),
                },
                records,
            )
            if not binding.get("source_record_id"):
                raise ValueError("issue_proof_source_record_required")
            authority_candidate = _safe_text(payload.get("authority_candidate") or "", limit=300)
            item = {
                "item_id": item_id,
                "issue_id": issue_id,
                "issue_label": issue_label,
                "proof_item_id": proof_item_id,
                "proof_label": proof_label,
                "evidence_role": evidence_role,
                "authority_candidate": authority_candidate,
                "authority_candidate_status": "not_provided" if not authority_candidate else "unverified_candidate",
                "authority_current_law_determined": False,
                **binding,
                "review_state": review_state,
                "reviewer_status": "review_required",
                "review_required": True,
                "notice": "This matrix organizes source-bound proof review. It does not determine legal elements, facts, sufficiency, jurisdiction, or filing readiness.",
            }
            entry = _history_entry(
                action="create",
                entity_type="issue_proof_item",
                entity_id=item_id,
                before=None,
                after=item,
                summary="Source-bound issue-to-proof matrix row recorded for human review.",
            )
            item["history"] = [entry]
            items[item_id] = item
            state["issue_proof_matrix"] = items
            state.setdefault("issue_proof_matrix_history", {})[item_id] = list(item["history"])
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "item": item, "review_required": True}

    def review_issue_proof_item(
        self, item_id: str, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            items = dict(state.get("issue_proof_matrix") or {})
            item = dict(items.get(item_id) or {})
            if not item:
                raise KeyError("issue_proof_item_not_found")
            before = dict(item)
            review_state = _safe_text(payload.get("review_state") or "review_required", limit=80)
            if review_state not in _ISSUE_PROOF_REVIEW_STATES:
                raise ValueError("issue_proof_review_state_invalid")
            binding = self._event_source_binding(
                {
                    "source_record_id": item.get("source_record_id"),
                    "source_hash": item.get("source_hash"),
                },
                records,
            )
            item.update(binding)
            item["review_state"] = review_state
            item["reviewer_notes"] = _safe_text(payload.get("reviewer_notes") or "", limit=2000)
            item["reviewer_status"] = "review_required"
            item["review_required"] = True
            entry = _history_entry(
                action="review",
                entity_type="issue_proof_item",
                entity_id=item_id,
                before=before,
                after=item,
                summary="Issue-to-proof matrix review state recorded without resolving proof sufficiency.",
            )
            item["history"] = list(item.get("history") or []) + [entry]
            items[item_id] = item
            state["issue_proof_matrix"] = items
            state.setdefault("issue_proof_matrix_history", {})[item_id] = list(item["history"])
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "item": item, "review_required": True}

    def issue_proof_matrix(self, item_id: str = "") -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            items = dict(state.get("issue_proof_matrix") or {})
            if item_id:
                item = dict(items.get(item_id) or {})
                if not item:
                    raise KeyError("issue_proof_item_not_found")
                return {
                    "status": "pass",
                    "item": item,
                    "history": list(state.get("issue_proof_matrix_history", {}).get(item_id) or []),
                    "review_required": True,
                }
            rows = sorted(items.values(), key=lambda row: (str(row.get("issue_id") or ""), str(row.get("proof_item_id") or ""), str(row.get("item_id") or "")))
            issue_rollup: dict[str, dict[str, Any]] = {}
            for row in rows:
                issue = issue_rollup.setdefault(
                    str(row.get("issue_id") or ""),
                    {"issue_id": row.get("issue_id"), "issue_label": row.get("issue_label"), "item_count": 0, "supports": 0, "contradicts": 0, "qualifies": 0, "missing_proof": 0, "unverified_authority_candidates": 0},
                )
                issue["item_count"] += 1
                role = str(row.get("evidence_role") or "")
                if role in issue:
                    issue[role] += 1
                if row.get("authority_candidate_status") == "unverified_candidate":
                    issue["unverified_authority_candidates"] += 1
            return {
                "status": "pass",
                "items": rows,
                "issues": list(issue_rollup.values()),
                "notice": "Proof, contradiction, missing-proof, and authority-candidate labels remain source-bound review aids. The matrix does not determine legal elements, facts, proof sufficiency, jurisdiction, or filing readiness.",
                "review_required": True,
            }

    def issue_proof_matrix_source(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            item = dict((state.get("issue_proof_matrix") or {}).get(item_id) or {})
            if not item:
                raise KeyError("issue_proof_item_not_found")
            return {"status": "pass", "item": item, "review_required": True}

    def _change_digest_snapshot(
        self, state: dict[str, Any], records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        rows, _warnings = self._records(records)
        record_manifest = {
            str(row.get("evidence_id") or ""): str(row.get("source_hash") or "").lower()
            for row in rows
            if str(row.get("evidence_id") or "") and str(row.get("source_hash") or "")
        }
        review_sections = (
            "timeline",
            "claims",
            "attachment_coverage",
            "fact_graph",
            "issue_proof_matrix",
            "missing_records",
            "ledger",
        )
        review_section_hashes = {
            section: _sha(state.get(section) or {}) for section in review_sections
        }
        contradiction_keys: list[dict[str, Any]] = []
        for claim_id, claim in sorted((state.get("claims") or {}).items()):
            for card_index, card in enumerate(claim.get("contradicts") or []):
                contradiction_keys.append(
                    {
                        "key": _sha({"claim_id": claim_id, "record_id": card.get("record_id"), "source_hash": card.get("source_hash"), "source_span": card.get("source_span")}),
                        "claim_id": claim_id,
                        "record_id": card.get("record_id"),
                        "source_hash": card.get("source_hash"),
                        "card_index": card_index,
                    }
                )
        calendar_review_items = [
            {
                "event_id": event.get("event_id"),
                "date_value": event.get("date_value"),
                "date_type": event.get("date_type"),
                "source_record_id": event.get("source_record_id"),
                "source_hash": event.get("source_hash"),
            }
            for event in (state.get("timeline") or {}).get("events") or []
            if str(event.get("date_type") or "") in {"hearing date", "service date", "filing date"}
        ]
        return {
            "record_manifest": record_manifest,
            "review_section_hashes": review_section_hashes,
            "candidate_contradictions": contradiction_keys,
            "calendar_review_items": calendar_review_items,
        }

    def create_change_digest_checkpoint(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            checkpoints = dict(state.get("change_digest_checkpoints") or {})
            checkpoint_id = _safe_text(payload.get("checkpoint_id") or "", limit=120)
            checkpoint_label = _safe_text(payload.get("checkpoint_label") or "", limit=300)
            if not checkpoint_id or not checkpoint_label:
                raise ValueError("change_digest_checkpoint_id_and_label_required")
            if checkpoint_id in checkpoints:
                raise ValueError("change_digest_checkpoint_id_exists")
            checkpoint = {
                "checkpoint_id": checkpoint_id,
                "checkpoint_label": checkpoint_label,
                "snapshot": self._change_digest_snapshot(state, records),
                "created_at": _utc_now(),
                "review_required": True,
                "notice": "A checkpoint is an operational comparison baseline. It does not approve work, determine whether a deadline applies, or resolve a factual or legal question.",
            }
            entry = _history_entry(
                action="create",
                entity_type="change_digest_checkpoint",
                entity_id=checkpoint_id,
                before=None,
                after=checkpoint,
                summary="Matter-change comparison checkpoint created from the active matter.",
            )
            checkpoint["history"] = [entry]
            checkpoints[checkpoint_id] = checkpoint
            state["change_digest_checkpoints"] = checkpoints
            state.setdefault("change_digest_history", {})[checkpoint_id] = []
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "checkpoint": checkpoint, "review_required": True}

    def matter_change_digest(
        self, checkpoint_id: str, *, records: Iterable[dict[str, Any]], persist: bool = True
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            checkpoint = dict((state.get("change_digest_checkpoints") or {}).get(checkpoint_id) or {})
            if not checkpoint:
                raise KeyError("change_digest_checkpoint_not_found")
            baseline = dict(checkpoint.get("snapshot") or {})
            current = self._change_digest_snapshot(state, records)
            baseline_records = dict(baseline.get("record_manifest") or {})
            current_records = dict(current.get("record_manifest") or {})
            new_records = [
                {"record_id": record_id, "source_hash": source_hash, "review_required": True}
                for record_id, source_hash in sorted(current_records.items())
                if record_id not in baseline_records
            ]
            changed_records = [
                {"record_id": record_id, "baseline_source_hash": source_hash, "current_source_hash": current_records[record_id], "review_required": True}
                for record_id, source_hash in sorted(baseline_records.items())
                if record_id in current_records and current_records[record_id] != source_hash
            ]
            unavailable_since_checkpoint = [
                {"record_id": record_id, "baseline_source_hash": source_hash, "review_required": True}
                for record_id, source_hash in sorted(baseline_records.items())
                if record_id not in current_records
            ]
            review_section_changes = [
                {"section": section, "baseline_hash": baseline_hash, "current_hash": current.get("review_section_hashes", {}).get(section), "review_required": True}
                for section, baseline_hash in sorted((baseline.get("review_section_hashes") or {}).items())
                if current.get("review_section_hashes", {}).get(section) != baseline_hash
            ]
            baseline_contradictions = {str(row.get("key") or "") for row in baseline.get("candidate_contradictions") or []}
            new_candidate_contradictions = [
                {**row, "review_required": True}
                for row in current.get("candidate_contradictions") or []
                if str(row.get("key") or "") not in baseline_contradictions
            ]
            baseline_calendar_keys = {
                _sha({"event_id": row.get("event_id"), "source_hash": row.get("source_hash"), "date_value": row.get("date_value")})
                for row in baseline.get("calendar_review_items") or []
            }
            new_calendar_review_items = [
                {**row, "review_required": True, "notice": "Date metadata needs human review; this does not calculate or determine a deadline."}
                for row in current.get("calendar_review_items") or []
                if _sha({"event_id": row.get("event_id"), "source_hash": row.get("source_hash"), "date_value": row.get("date_value")}) not in baseline_calendar_keys
            ]
            stale_work = [
                {"scope": "record", "record_id": row["record_id"], "reason": "record_changed_or_unavailable_since_checkpoint", "review_required": True}
                for row in changed_records + unavailable_since_checkpoint
            ] + [
                {"scope": "review_work", "section": row["section"], "reason": "source_bound_review_work_changed_since_checkpoint", "review_required": True}
                for row in review_section_changes
            ]
            digest = {
                "digest_id": _safe_id("change-digest", checkpoint_id, _sha(current)),
                "checkpoint_id": checkpoint_id,
                "checkpoint_label": checkpoint.get("checkpoint_label"),
                "generated_at": _utc_now(),
                "new_records": new_records,
                "changed_records": changed_records,
                "unavailable_since_checkpoint": unavailable_since_checkpoint,
                "review_section_changes": review_section_changes,
                "new_candidate_contradictions": new_candidate_contradictions,
                "new_calendar_review_items": new_calendar_review_items,
                "stale_work": stale_work,
                "notice": "This change digest compares active-matter records and review-work snapshots. It does not identify altered conclusions, resolve contradictions, calculate deadlines, determine legal effect, or approve work.",
                "review_required": True,
            }
            if persist:
                entry = _history_entry(
                    action="generate",
                    entity_type="matter_change_digest",
                    entity_id=digest["digest_id"],
                    before=None,
                    after=digest,
                    summary="Matter-change digest generated from a source-bound checkpoint.",
                )
                digest["history_entry"] = entry
                state.setdefault("change_digest_history", {}).setdefault(checkpoint_id, []).append(digest)
                state.setdefault("review_history", []).append(entry)
                self._append_history_log(entry)
                self._save_state(state)
            return {"status": "pass", "digest": digest, "review_required": True}

    def change_digest_checkpoints(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            checkpoints = sorted((state.get("change_digest_checkpoints") or {}).values(), key=lambda row: str(row.get("checkpoint_id") or ""))
            return {"status": "pass", "checkpoints": checkpoints, "review_required": True}

    def change_digest_record_source(
        self, checkpoint_id: str, record_id: str, *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            checkpoint = dict((state.get("change_digest_checkpoints") or {}).get(checkpoint_id) or {})
            if not checkpoint:
                raise KeyError("change_digest_checkpoint_not_found")
            baseline_manifest = (checkpoint.get("snapshot") or {}).get("record_manifest", {})
            current_manifest = self._change_digest_snapshot(state, records).get("record_manifest", {})
            if record_id not in baseline_manifest and record_id not in current_manifest:
                raise KeyError("change_digest_record_not_found")
            source_hash = str(current_manifest.get(record_id) or "").lower()
            if not source_hash:
                raise ValueError("change_digest_source_record_unavailable")
            return {"status": "pass", "checkpoint_id": checkpoint_id, "record_id": record_id, "source_hash": source_hash, "review_required": True}

    def _lineage_record_binding(
        self, record_id: Any, supplied_hash: Any, records: Iterable[dict[str, Any]], *, field_name: str
    ) -> dict[str, Any]:
        binding = self._event_source_binding(
            {"source_record_id": record_id, "source_hash": supplied_hash}, records
        )
        if not binding.get("source_record_id"):
            raise ValueError(f"record_lineage_{field_name}_required")
        return {
            "record_id": binding["source_record_id"],
            "source_hash": binding["source_hash"],
            "source_block": binding.get("source_block") or {},
        }

    def create_record_lineage_link(
        self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            links = dict(state.get("record_lineage") or {})
            link_id = _safe_text(payload.get("link_id") or "", limit=120)
            relationship = _safe_text(payload.get("relationship") or "", limit=80)
            if not link_id:
                raise ValueError("record_lineage_link_id_required")
            if link_id in links:
                raise ValueError("record_lineage_link_id_exists")
            if relationship not in _RECORD_LINEAGE_RELATIONSHIPS:
                raise ValueError("record_lineage_relationship_invalid")
            original = self._lineage_record_binding(
                payload.get("original_record_id"), payload.get("original_source_hash"), records, field_name="original_record"
            )
            derivative = self._lineage_record_binding(
                payload.get("derivative_record_id"), payload.get("derivative_source_hash"), records, field_name="derivative_record"
            )
            if original["record_id"] == derivative["record_id"]:
                raise ValueError("record_lineage_records_must_differ")
            link = {
                "link_id": link_id,
                "relationship": relationship,
                "original": original,
                "derivative": derivative,
                "reviewer_notes": _safe_text(payload.get("reviewer_notes") or "", limit=2000),
                "reviewer_status": "review_required",
                "review_required": True,
                "notice": "This is a proposed source-provenance relationship. It does not decide authenticity, admissibility, completeness, legal effect, or which record controls.",
            }
            entry = _history_entry(
                action="create", entity_type="record_lineage_link", entity_id=link_id,
                before=None, after=link,
                summary="Source-bound record lineage relationship recorded for human review.",
            )
            link["history"] = [entry]
            links[link_id] = link
            state["record_lineage"] = links
            state.setdefault("record_lineage_history", {})[link_id] = list(link["history"])
            state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry)
            self._save_state(state)
            return {"status": "pass", "link": link, "review_required": True}

    def record_lineage(self, link_id: str = "") -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            links = dict(state.get("record_lineage") or {})
            if link_id:
                link = dict(links.get(link_id) or {})
                if not link:
                    raise KeyError("record_lineage_link_not_found")
                return {"status": "pass", "link": link, "history": list(state.get("record_lineage_history", {}).get(link_id) or []), "review_required": True}
            rows = sorted(links.values(), key=lambda row: str(row.get("link_id") or ""))
            relationship_counts = {name: 0 for name in sorted(_RECORD_LINEAGE_RELATIONSHIPS)}
            for row in rows:
                relationship = str(row.get("relationship") or "")
                if relationship in relationship_counts:
                    relationship_counts[relationship] += 1
            return {"status": "pass", "links": rows, "relationship_counts": relationship_counts, "notice": "Record lineage links are review-required provenance proposals, not determinations of authenticity, legal effect, or controlling text.", "review_required": True}

    def record_lineage_source(self, link_id: str, side: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            link = dict((state.get("record_lineage") or {}).get(link_id) or {})
            if not link:
                raise KeyError("record_lineage_link_not_found")
            if side not in {"original", "derivative"}:
                raise ValueError("record_lineage_side_invalid")
            binding = dict(link.get(side) or {})
            if not binding.get("record_id") or not binding.get("source_hash"):
                raise ValueError("record_lineage_source_unbound")
            return {"status": "pass", "link_id": link_id, "side": side, "binding": binding, "review_required": True}

    def create_entity_resolution_candidate(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state(); candidates = dict(state.get("entity_resolution") or {})
            candidate_id = _safe_text(payload.get("candidate_id") or "", limit=120)
            entity_label = _safe_text(payload.get("entity_label") or "", limit=300)
            entity_type = _safe_text(payload.get("entity_type") or "person", limit=80)
            if not candidate_id or not entity_label:
                raise ValueError("entity_resolution_candidate_id_and_label_required")
            if candidate_id in candidates:
                raise ValueError("entity_resolution_candidate_id_exists")
            if entity_type not in _ENTITY_RESOLUTION_TYPES:
                raise ValueError("entity_resolution_type_invalid")
            left = self._lineage_record_binding(payload.get("left_record_id"), payload.get("left_source_hash"), records, field_name="left_record")
            right = self._lineage_record_binding(payload.get("right_record_id"), payload.get("right_source_hash"), records, field_name="right_record")
            if left["record_id"] == right["record_id"]:
                raise ValueError("entity_resolution_records_must_differ")
            candidate = {"candidate_id": candidate_id, "entity_label": entity_label, "entity_type": entity_type, "left": left, "right": right, "reviewer_notes": _safe_text(payload.get("reviewer_notes") or "", limit=2000), "resolution_status": "review_required", "merge_status": "not_merged", "review_required": True, "notice": "This is a source-bound possible-identity review item. It does not infer identity, alter original records, merge data, or make a factual finding until an explicit human confirmation is recorded."}
            entry = _history_entry(action="create", entity_type="entity_resolution_candidate", entity_id=candidate_id, before=None, after=candidate, summary="Cross-document entity candidate recorded for explicit human review.")
            candidate["history"] = [entry]; candidates[candidate_id] = candidate
            state["entity_resolution"] = candidates; state.setdefault("entity_resolution_history", {})[candidate_id] = list(candidate["history"]); state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry); self._save_state(state)
            return {"status": "pass", "candidate": candidate, "review_required": True}

    def confirm_entity_resolution(self, candidate_id: str, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state(); candidates = dict(state.get("entity_resolution") or {}); candidate = dict(candidates.get(candidate_id) or {})
            if not candidate: raise KeyError("entity_resolution_candidate_not_found")
            if _safe_text(payload.get("confirmation") or "", limit=80) != "confirm_same_entity":
                raise ValueError("entity_resolution_explicit_confirmation_required")
            before = dict(candidate)
            for side in ("left", "right"):
                binding = dict(candidate.get(side) or {})
                candidate[side] = self._lineage_record_binding(binding.get("record_id"), binding.get("source_hash"), records, field_name=f"{side}_record")
            candidate["resolution_status"] = "human_confirmed_same_entity"
            candidate["merge_status"] = "logical_merge_active"
            candidate["canonical_entity_id"] = _safe_text(payload.get("canonical_entity_id") or candidate_id, limit=120)
            candidate["reviewer_notes"] = _safe_text(payload.get("reviewer_notes") or "", limit=2000)
            candidate["review_required"] = True
            entry = _history_entry(action="confirm", entity_type="entity_resolution_candidate", entity_id=candidate_id, before=before, after=candidate, summary="Explicit human confirmation recorded; logical merge remains reversible and review-required.")
            candidate["history"] = list(candidate.get("history") or []) + [entry]; candidates[candidate_id] = candidate
            state["entity_resolution"] = candidates; state.setdefault("entity_resolution_history", {})[candidate_id] = list(candidate["history"]); state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry); self._save_state(state)
            return {"status": "pass", "candidate": candidate, "review_required": True}

    def revoke_entity_resolution(self, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state(); candidates = dict(state.get("entity_resolution") or {}); candidate = dict(candidates.get(candidate_id) or {})
            if not candidate: raise KeyError("entity_resolution_candidate_not_found")
            if candidate.get("merge_status") != "logical_merge_active": raise ValueError("entity_resolution_no_active_merge")
            before = dict(candidate); candidate["resolution_status"] = "confirmation_revoked"; candidate["merge_status"] = "reversed"; candidate["reviewer_notes"] = _safe_text(payload.get("reviewer_notes") or "", limit=2000); candidate["review_required"] = True
            entry = _history_entry(action="revoke", entity_type="entity_resolution_candidate", entity_id=candidate_id, before=before, after=candidate, summary="Logical merge revoked; source records were never altered.")
            candidate["history"] = list(candidate.get("history") or []) + [entry]; candidates[candidate_id] = candidate
            state["entity_resolution"] = candidates; state.setdefault("entity_resolution_history", {})[candidate_id] = list(candidate["history"]); state.setdefault("review_history", []).append(entry)
            self._append_history_log(entry); self._save_state(state)
            return {"status": "pass", "candidate": candidate, "review_required": True}

    def entity_resolution(self, candidate_id: str = "") -> dict[str, Any]:
        with self._lock:
            state = self._load_state(); candidates = dict(state.get("entity_resolution") or {})
            if candidate_id:
                candidate = dict(candidates.get(candidate_id) or {})
                if not candidate: raise KeyError("entity_resolution_candidate_not_found")
                return {"status": "pass", "candidate": candidate, "history": list(state.get("entity_resolution_history", {}).get(candidate_id) or []), "review_required": True}
            rows = sorted(candidates.values(), key=lambda row: str(row.get("candidate_id") or ""))
            return {"status": "pass", "candidates": rows, "notice": "Possible identity matches need explicit human confirmation. Logical merges are reversible and never modify original records.", "review_required": True}

    def entity_resolution_source(self, candidate_id: str, side: str) -> dict[str, Any]:
        candidate = self.entity_resolution(candidate_id).get("candidate") or {}
        if side not in {"left", "right"}: raise ValueError("entity_resolution_side_invalid")
        binding = dict(candidate.get(side) or {})
        if not binding.get("record_id") or not binding.get("source_hash"): raise ValueError("entity_resolution_source_unbound")
        return {"status": "pass", "candidate_id": candidate_id, "side": side, "binding": binding, "review_required": True}

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

    def matter_completeness(self, *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Explain operational coverage without forecasting a case result."""
        coverage = self.coverage(records=records)
        with self._lock:
            state = self._load_state()
            dimensions = {
                "record_inventory": {"observed": coverage["searchable_records"], "blocker": "no_searchable_records" if not coverage["searchable_records"] else ""},
                "date_review": {"observed": len(coverage["records_by_date"]), "blocker": "undated_records_need_review" if coverage["undated_records"] else ""},
                "source_integrity": {"observed": coverage["searchable_records"] - len(coverage["parser_ocr_failures"]), "blocker": "parser_or_ocr_review_required" if coverage["parser_ocr_failures"] else ""},
                "missing_record_review": {"observed": len(state.get("missing_records") or {}), "blocker": "missing_record_items_open" if state.get("missing_records") else ""},
                "issue_proof_review": {"observed": len(state.get("issue_proof_matrix") or {}), "blocker": "issue_proof_items_need_human_review" if state.get("issue_proof_matrix") else ""},
            }
            blockers = [row["blocker"] for row in dimensions.values() if row["blocker"]]
            return {"status":"pass","dimensions":dimensions,"blockers":blockers,"notice":"Completeness dimensions describe observed record and review-work coverage only. They do not score a case, predict an outcome, assess legal sufficiency, or approve filing.","review_required":True}

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
