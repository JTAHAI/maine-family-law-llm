from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from legal.security.durable_io import atomic_write_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor

SCHEMA_VERSION = "communications_parenting_time_workbench_v1"
WORKSPACE_FOLDER = "22_COMMUNICATIONS_PARENTING_TIME_WORKBENCH"
MAX_MESSAGES = 20_000
MAX_THREADS = 5_000
MAX_EXPORTS = 500
MAX_HISTORY = 20_000
MAX_TEXT = 20_000
_LOCK = threading.RLock()
_CREDENTIAL_KEYS = {
    "credentials",
    "credential",
    "oauth",
    "oauth_token",
    "access_token",
    "refresh_token",
    "auth_token",
    "password",
    "api_key",
    "secret",
}
_MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9._:@+-]{4,256}$")
_RE_PREFIX_RE = re.compile(r"^(?:re|fw|fwd)\s*:\s*", re.IGNORECASE)
_QUOTE_RE = re.compile(r"^on .+ wrote:$", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class CommunicationsWorkbenchError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class CommunicationsArtifact:
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


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: Any) -> str:
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _safe_text(value: Any, *, limit: int = MAX_TEXT) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _ensure_list(value: Any, *, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _safe_id(prefix: str, *parts: Any) -> str:
    payload = "\0".join(_safe_text(part, limit=1_000) for part in parts)
    return f"{prefix}-{_sha(payload)[:16]}"


def _parse_dt(value: Any, timezone_name: str | None = None) -> tuple[str | None, str, str | None]:
    raw = _safe_text(value, limit=120)
    if not raw:
        return None, "unknown", None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, "unknown", raw
    timezone_status = "explicit" if parsed.tzinfo else "unknown"
    zone_label = None
    if parsed.tzinfo is None and timezone_name:
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = None
        if zone is not None:
            fold0 = parsed.replace(tzinfo=zone, fold=0)
            fold1 = parsed.replace(tzinfo=zone, fold=1)
            if fold0.utcoffset() != fold1.utcoffset():
                timezone_status = "ambiguous"
            else:
                timezone_status = "assumed"
            parsed = fold0
            zone_label = timezone_name
    elif parsed.tzinfo is not None:
        zone_label = parsed.tzinfo.tzname(parsed) if parsed.tzinfo else None
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z"), timezone_status, zone_label


def _normalize_subject(subject: Any) -> str:
    raw = _safe_text(subject, limit=240)
    while True:
        next_value = _RE_PREFIX_RE.sub("", raw).strip()
        if next_value == raw:
            return next_value.casefold()
        raw = next_value


def _body_excerpt(text: str, *, limit: int = 280) -> str:
    return _safe_text(text, limit=limit)


def _participant_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        items = []
    return [item for item in items if item][:20]


def _contains_attachment_signal(body: str) -> bool:
    lowered = f" {body.casefold()} "
    return any(term in lowered for term in (" attached ", " attachment ", " see attached ", " attached file ", " enclosed "))


def _detect_quote_blocks(body: str) -> list[str]:
    lines = [line.rstrip() for line in body.splitlines()]
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith(">") or _QUOTE_RE.match(line.strip()):
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current).strip())
            current = []
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _message_fingerprint(row: dict[str, Any]) -> str:
    return _sha(
        {
            "message_id": row.get("message_id"),
            "source_hash": row.get("source_hash"),
            "subject": row.get("subject"),
            "body": row.get("body"),
            "sent_at": row.get("sent_at"),
            "from": row.get("from"),
            "to": row.get("to"),
        }
    )


def _thread_subject_key(row: dict[str, Any]) -> str:
    return _normalize_subject(row.get("subject")) or _safe_text(row.get("thread_id") or row.get("source_id") or row.get("message_id"), limit=120).casefold()


def _classify_message(row: dict[str, Any]) -> dict[str, Any]:
    body = str(row.get("body") or "")
    body_lower = f" {body.casefold()} "
    kind = "communication"
    if any(term in body_lower for term in (" court order ", " court order,", " according to the court order ", " according to the order ", " the order says ", " per the order ", " per the court order ")):
        kind = "court_order"
    elif any(term in body_lower for term in (" can we switch ", " would you agree to switch ", " propose ", " proposal ", " can we move ", " would you be willing ")):
        kind = "proposal"
    elif any(term in body_lower for term in (" yes ", " agreed ", " confirmed ", " sounds good ", " works for me ", " okay to ", " okay, we can ")):
        kind = "confirmation"
    elif any(term in body_lower for term in (" no ", " cannot ", " can't ", " won't ", " refuse ", " disagre", " not okay ")):
        kind = "disagreement"
    elif any(term in body_lower for term in (" running late ", " delayed ", " stuck in traffic ", " will be late ", " arriving late ")):
        kind = "delay_notice"
    elif any(term in body_lower for term in (" missed exchange ", " did not show ", " no-show ", " not picked up ", " no pickup ")):
        kind = "alleged_missed_exchange"
    elif any(term in body_lower for term in (" informally ", " off the record ", " not changing the order ", " temporary change ", " flexible ")):
        kind = "informal_change"
    if kind == "proposal" and any(
        term in body_lower
        for term in (
            " silence ",
            " no response ",
            " not a response ",
            " because you did not reply ",
            " if you don't reply ",
            " if you do not reply ",
            " assuming you are not agreeing ",
            " assuming no reply ",
        )
    ):
        kind = "silence_not_agreement"
    if kind == "communication":
        if row.get("source_type") in {"calendar", "calendar_event"}:
            kind = "calendar"
        elif row.get("source_type") in {"call", "call_log"}:
            kind = "call_log"
        elif row.get("source_type") in {"school", "childcare", "medical", "transportation"}:
            kind = str(row.get("source_type"))
    return {"kind": kind}


class CommunicationsWorkbenchStore:
    def __init__(self, case_root: Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.exists() or not self.case_root.is_dir():
            raise CommunicationsWorkbenchError("case_root_unavailable", "The active case workspace is unavailable.", status_code=409)
        self.root = self.case_root / WORKSPACE_FOLDER
        self.imports_dir = self.root / "imports"
        self.exports_dir = self.root / "exports"
        self.state_path = self.root / "communications-workbench.json.enc"
        self.history_path = self.root / "communications-history.jsonl"
        self._lock = threading.RLock()
        self._encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MFL_COMMUNICATIONS_KEY") or "communications-local-development-key"
        )
        for folder in (self.root, self.imports_dir, self.exports_dir):
            if folder.exists() and folder.is_symlink():
                raise CommunicationsWorkbenchError("workspace_symlink_refused", "A communications workspace symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": self.case_root.name,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "messages": [],
            "threads": [],
            "schedule_history": [],
            "parenting_time_events": [],
            "agreements": [],
            "claims": [],
            "completeness": {},
            "exports": [],
            "history": [],
            "imports": [],
            "review_required": True,
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        return self._encryptor.decrypt_json(payload)

    def _save_state(self, state: dict[str, Any]) -> None:
        state = dict(state)
        state["updated_at"] = _utc_now()
        envelope = self._encryptor.encrypt_json(state)
        atomic_write_bytes(self.state_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))

    def _append_history(self, state: dict[str, Any], *, action: str, entity_type: str, entity_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None, summary: str) -> dict[str, Any]:
        entry = {
            "history_id": _safe_id("hist", action, entity_type, entity_id, secrets.token_hex(4), _utc_now()),
            "generated_at": _utc_now(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before_sha256": _sha(before or {}),
            "after_sha256": _sha(after or {}),
            "summary": summary[:1000],
            "review_required": True,
        }
        history = list(state.get("history") or [])
        history.append(entry)
        state["history"] = history[-MAX_HISTORY:]
        return entry

    def _normalize_import_item(self, raw: dict[str, Any], *, source_index: int) -> dict[str, Any]:
        if any(key in raw for key in _CREDENTIAL_KEYS):
            raise CommunicationsWorkbenchError("credentials_not_supported", "Credentials are not accepted in the local communications workbench.", status_code=400)
        raw_body = str(raw.get("body") or raw.get("text") or raw.get("content") or "").replace("\x00", "")
        body = raw_body.strip()[:10_000]
        sent_at, timezone_status, zone_label = _parse_dt(raw.get("sent_at") or raw.get("timestamp") or raw.get("date"), str(raw.get("timezone") or raw.get("time_zone") or "") or None)
        source_hash = _safe_text(raw.get("source_hash") or raw.get("sha256") or "", limit=64).lower()
        if source_hash and len(source_hash) != 64:
            source_hash = _sha(body)
        attachments = []
        for attachment in _ensure_list(raw.get("attachments"), limit=40):
            if not isinstance(attachment, dict):
                continue
            attachments.append(
                {
                    "name": _safe_text(attachment.get("name") or attachment.get("filename") or attachment.get("title"), limit=240),
                    "sha256": _safe_text(attachment.get("sha256") or attachment.get("source_hash") or "", limit=64).lower(),
                    "size_bytes": max(0, int(attachment.get("size_bytes") or attachment.get("bytes") or 0)),
                    "content_type": _safe_text(attachment.get("content_type") or attachment.get("mime_type") or "application/octet-stream", limit=120),
                }
            )
        quoted_blocks = _detect_quote_blocks(body)
        source_id = _safe_text(raw.get("source_id") or raw.get("record_id") or raw.get("message_id") or source_index, limit=120)
        message_id = _safe_text(raw.get("message_id") or raw.get("id") or _safe_id("msg", source_id, body, sent_at), limit=120)
        if not _MESSAGE_ID_RE.fullmatch(message_id):
            message_id = _safe_id("msg", source_id, body, sent_at)
        thread_id = _safe_text(raw.get("thread_id") or raw.get("conversation_id") or "", limit=120)
        participants = {
            "from": _participant_list(raw.get("from") or raw.get("sender")),
            "to": _participant_list(raw.get("to")),
            "cc": _participant_list(raw.get("cc")),
            "bcc": _participant_list(raw.get("bcc")),
        }
        thread_references = _ensure_list(raw.get("references"), limit=20)
        reply_to = _safe_text(raw.get("in_reply_to") or raw.get("reply_to") or "", limit=120)
        body_excerpt = _body_excerpt(body, limit=320)
        kind = _classify_message(
            {
                "source_type": raw.get("source_type"),
                "body": body,
            }
        )["kind"]
        return {
            "message_id": message_id,
            "source_id": source_id,
            "source_type": _safe_text(raw.get("source_type") or "message", limit=40),
            "channel": _safe_text(raw.get("channel") or raw.get("source_type") or "message", limit=40),
            "source_label": _safe_text(raw.get("source_label") or raw.get("title") or raw.get("subject") or message_id, limit=300),
            "source_hash": source_hash or _sha(body or message_id),
            "source_span": raw.get("source_span") if isinstance(raw.get("source_span"), dict) else None,
            "subject": _safe_text(raw.get("subject") or raw.get("title") or "", limit=240),
            "body": body,
            "body_excerpt": body_excerpt,
            "sent_at": sent_at,
            "timezone_status": timezone_status,
            "timezone_label": zone_label,
            "participants": participants,
            "attachments": attachments,
            "attachment_count": len(attachments),
            "attachment_missing": bool(_contains_attachment_signal(body) and not attachments),
            "message_kind": kind,
            "quoted_blocks": quoted_blocks,
            "quoted_block_count": len(quoted_blocks),
            "thread_id": thread_id,
            "in_reply_to": reply_to,
            "references": [str(item)[:120] for item in thread_references if str(item).strip()],
            "duplicate_group": _safe_text(raw.get("source_hash") or _sha({"subject": _normalize_subject(raw.get("subject")), "body": body, "sender": participants["from"][:1], "to": participants["to"][:4]}), limit=64).lower(),
            "review_required": True,
        }

    def _thread_key(self, message: dict[str, Any]) -> tuple[str, str]:
        if message.get("thread_id"):
            return str(message["thread_id"]), "explicit_thread_id"
        references = [str(item) for item in message.get("references") or [] if str(item).strip()]
        if message.get("in_reply_to"):
            references.append(str(message["in_reply_to"]))
        if references:
            return f"refs:{references[-1]}", "reply_chain"
        subject_key = _thread_subject_key(message)
        if subject_key:
            return f"subject:{subject_key}", "subject_normalization"
        return f"message:{message['message_id']}", "fallback_message_id"

    def _build_threads(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        reason_by_key: dict[str, str] = {}
        for message in messages:
            key, reason = self._thread_key(message)
            grouped.setdefault(key, []).append(message)
            reason_by_key.setdefault(key, reason)
        threads: list[dict[str, Any]] = []
        for thread_key, rows in grouped.items():
            rows = sorted(rows, key=lambda row: (str(row.get("sent_at") or ""), str(row.get("message_id") or "")))
            subject = rows[0].get("subject") or rows[0].get("source_label") or thread_key
            participants = sorted({participant for row in rows for values in row.get("participants", {}).values() for participant in values})
            explicit = reason_by_key.get(thread_key) == "explicit_thread_id"
            confidence = 1.0 if explicit else 0.78 if reason_by_key.get(thread_key) == "reply_chain" else 0.62
            alternatives: list[dict[str, Any]] = []
            if reason_by_key.get(thread_key) == "subject_normalization" and len(rows) > 1:
                confidence = 0.52
                alternatives.append({
                    "reason": "subject_only_grouping",
                    "possible_thread_count": len(rows),
                    "possible_message_ids": [row["message_id"] for row in rows[:5]],
                })
            thread = {
                "thread_id": thread_key.replace(":", "-", 1),
                "thread_key": thread_key,
                "thread_reason": reason_by_key.get(thread_key, "fallback_message_id"),
                "subject": subject,
                "message_count": len(rows),
                "participants": participants,
                "confidence": round(confidence, 2),
                "alternatives": alternatives,
                "messages": [self._message_card(row) for row in rows],
                "review_required": True,
            }
            threads.append(thread)
        threads.sort(key=lambda row: (row["thread_reason"], row["thread_id"]))
        return threads[:MAX_THREADS]

    def _message_card(self, message: dict[str, Any]) -> dict[str, Any]:
        return {
            "message_id": message["message_id"],
            "source_id": message["source_id"],
            "source_type": message["source_type"],
            "source_label": message["source_label"],
            "source_hash": message["source_hash"],
            "source_span": message.get("source_span"),
            "subject": message["subject"],
            "sent_at": message["sent_at"],
            "timezone_status": message["timezone_status"],
            "timezone_label": message["timezone_label"],
            "message_kind": message["message_kind"],
            "body_excerpt": message["body_excerpt"],
            "attachment_count": message["attachment_count"],
            "attachment_missing": message["attachment_missing"],
            "quoted_block_count": message["quoted_block_count"],
            "duplicate_group": message["duplicate_group"],
            "review_required": True,
        }

    def _build_schedule_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for message in messages:
            text = f" {message['body'].casefold()} "
            if message["message_kind"] not in {"communication", "calendar", "call_log", "court_order", "proposal", "confirmation", "disagreement", "delay_notice", "informal_change", "alleged_missed_exchange"}:
                continue
            if any(term in text for term in (" pickup ", " dropoff ", " drop-off ", " exchange ", " parenting time ", " visitation ", " parenting-time ")):
                event_kind = "parenting_time_change"
            elif any(term in text for term in (" school ", " daycare ", " childcare ", " doctor ", " appointment ")):
                event_kind = "supporting_coordination"
            else:
                event_kind = "communication"
            if message["message_kind"] == "court_order":
                event_kind = "court_order"
            elif message["message_kind"] in {"proposal", "confirmation", "disagreement", "delay_notice", "informal_change", "alleged_missed_exchange"}:
                event_kind = message["message_kind"]
            status = "review_required"
            if message["message_kind"] == "confirmation":
                status = "confirmed"
            elif message["message_kind"] == "disagreement":
                status = "disputed"
            elif message["message_kind"] == "delay_notice":
                status = "delay_not_refusal"
            elif message["message_kind"] == "informal_change":
                status = "informal_change_only"
            elif message["message_kind"] == "court_order":
                status = "order_controlling"
            elif message["message_kind"] == "alleged_missed_exchange":
                status = "alleged"
            elif message["message_kind"] == "proposal":
                status = "proposal_only"
            elif message["message_kind"] == "silence_not_agreement":
                status = "silence_not_agreement"
            rows.append(
                {
                    "event_id": _safe_id("sched", message["message_id"], message["source_hash"]),
                    "message_id": message["message_id"],
                    "thread_id": message.get("thread_id") or None,
                    "event_kind": event_kind,
                    "status": status,
                    "operative_order": message["message_kind"] == "court_order",
                    "source_ref": self._source_ref(message),
                    "source_excerpt": message["body_excerpt"],
                    "exact_span": message.get("source_span"),
                    "review_required": True,
                }
            )
        return rows[:MAX_MESSAGES]

    def _build_parenting_time_events(self, schedule_history: list[dict[str, Any]], messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for row in schedule_history:
            if row["event_kind"] in {"court_order", "parenting_time_change", "proposal", "confirmation", "disagreement", "delay_notice", "informal_change", "alleged_missed_exchange"}:
                events.append(
                    {
                        "event_id": row["event_id"],
                        "kind": row["event_kind"],
                        "status": row["status"],
                        "operative_order": row["operative_order"],
                        "source_ref": row["source_ref"],
                        "source_excerpt": row["source_excerpt"],
                        "review_required": True,
                    }
                )
        if not events:
            for message in messages:
                if message["message_kind"] in {"calendar", "call_log", "school", "childcare", "medical", "transportation"}:
                    events.append(
                        {
                            "event_id": _safe_id("event", message["message_id"]),
                            "kind": message["message_kind"],
                            "status": "informational",
                            "operative_order": False,
                            "source_ref": self._source_ref(message),
                            "source_excerpt": message["body_excerpt"],
                            "review_required": True,
                        }
                    )
        return events[:MAX_MESSAGES]

    def _build_agreements(self, messages: list[dict[str, Any]], schedule_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_message = {row["message_id"]: row for row in messages}
        agreements: list[dict[str, Any]] = []
        for row in schedule_history:
            if row["status"] in {"confirmed", "order_controlling", "informal_change_only", "silence_not_agreement", "delay_not_refusal"}:
                message = by_message.get(row["message_id"], {})
                agreements.append(
                    {
                        "agreement_id": _safe_id("agree", row["event_id"]),
                        "message_id": row["message_id"],
                        "status": row["status"],
                        "kind": row["event_kind"],
                        "operative_order": row["operative_order"],
                        "source_ref": self._source_ref(message),
                        "review_required": True,
                    }
                )
        return agreements[:MAX_MESSAGES]

    def _build_claims(self, messages: list[dict[str, Any]], schedule_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        for row in schedule_history:
            if row["status"] not in {"disputed", "alleged", "proposal_only", "silence_not_agreement", "delay_not_refusal"}:
                continue
            claims.append(
                {
                    "claim_id": _safe_id("claim", row["event_id"]),
                    "claim_type": row["status"],
                    "message_id": row["message_id"],
                    "kind": row["event_kind"],
                    "support": [row["source_ref"]],
                    "contradiction": [],
                    "qualification": "review_required",
                    "alternatives": ["The record stays review_required and no broader conclusion is drawn."],
                    "missing_context": [],
                    "reviewer_decision": "needs_review",
                    "review_required": True,
                }
            )
        if not claims and messages:
            claims.append(
                {
                    "claim_id": _safe_id("claim", messages[0]["message_id"], "fallback"),
                    "claim_type": "communication_review",
                    "message_id": messages[0]["message_id"],
                    "kind": messages[0]["message_kind"],
                    "support": [self._source_ref(messages[0])],
                    "contradiction": [],
                    "qualification": "review_required",
                    "alternatives": [],
                    "missing_context": [],
                    "reviewer_decision": "needs_review",
                    "review_required": True,
                }
            )
        return claims[:MAX_MESSAGES]

    def _build_completeness(self, messages: list[dict[str, Any]], threads: list[dict[str, Any]], schedule_history: list[dict[str, Any]]) -> dict[str, Any]:
        counts_by_type: dict[str, int] = {}
        missing_attachments = [row for row in messages if row["attachment_missing"]]
        timezone_unknown = [row for row in messages if row["timezone_status"] in {"unknown", "ambiguous"}]
        duplicate_groups: dict[str, list[str]] = {}
        for row in messages:
            duplicate_groups.setdefault(row["duplicate_group"], []).append(row["message_id"])
        exact_duplicate_groups = [
            {"duplicate_group": key, "message_ids": ids, "duplicate_count": len(ids)}
            for key, ids in duplicate_groups.items()
            if len(ids) > 1
        ]
        for row in messages:
            counts_by_type[row["source_type"]] = counts_by_type.get(row["source_type"], 0) + 1
        return {
            "status": "review_required" if missing_attachments or timezone_unknown or exact_duplicate_groups else "pass",
            "message_count": len(messages),
            "thread_count": len(threads),
            "source_type_counts": counts_by_type,
            "missing_attachments": [
                {
                    "message_id": row["message_id"],
                    "source_ref": self._source_ref(row),
                    "source_excerpt": row["body_excerpt"],
                }
                for row in missing_attachments
            ],
            "timezone_unknown": [
                {
                    "message_id": row["message_id"],
                    "timezone_status": row["timezone_status"],
                    "source_ref": self._source_ref(row),
                }
                for row in timezone_unknown
            ],
            "duplicate_groups": exact_duplicate_groups,
            "review_required": True,
            "no_sentiment_or_fitness_inference": True,
            "no_parent_ranking": True,
            "no_abuse_conclusion": True,
        }

    def _rebuild(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = sorted(list(state.get("messages") or [])[:MAX_MESSAGES], key=lambda row: (str(row.get("sent_at") or ""), str(row.get("message_id") or "")))
        threads = self._build_threads(messages)
        schedule_history = self._build_schedule_history(messages)
        parenting_time_events = self._build_parenting_time_events(schedule_history, messages)
        agreements = self._build_agreements(messages, schedule_history)
        claims = self._build_claims(messages, schedule_history)
        completeness = self._build_completeness(messages, threads, schedule_history)
        state.update(
            {
                "messages": messages,
                "threads": threads,
                "schedule_history": schedule_history,
                "parenting_time_events": parenting_time_events,
                "agreements": agreements,
                "claims": claims,
                "completeness": completeness,
            }
        )
        return state

    def _source_ref(self, row: dict[str, Any]) -> dict[str, Any]:
        ref: dict[str, Any] = {}
        for key in ("source_id", "source_type", "source_hash", "source_span", "source_label", "source_excerpt", "body_excerpt", "sent_at", "timezone_status"):
            if row.get(key) is not None:
                ref[key] = row.get(key)
        return ref

    def _import_entry(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        items = payload.get("messages") or payload.get("records") or payload.get("items") or []
        if not isinstance(items, list):
            raise CommunicationsWorkbenchError("import_payload_invalid", "The import payload is invalid.", status_code=400)
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(items[:MAX_MESSAGES]):
            if not isinstance(raw, dict):
                continue
            normalized.append(self._normalize_import_item(raw, source_index=index))
        if not normalized:
            raise CommunicationsWorkbenchError("no_importable_items", "No communications records were supplied.", status_code=400)
        entry = {
            "import_id": _safe_id("import", _utc_now(), len(normalized), secrets.token_hex(4)),
            "generated_at": _utc_now(),
            "item_count": len(normalized),
            "source_type_counts": self._source_type_counts(normalized),
            "source_hash": _sha([row["source_hash"] for row in normalized]),
            "review_required": True,
        }
        return normalized, entry

    @staticmethod
    def _source_type_counts(messages: Iterable[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in messages:
            counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1
        return counts

    def import_communications(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            before = json.loads(json.dumps(state))
            normalized, import_entry = self._import_entry(payload)
            existing = {row["message_id"]: row for row in state.get("messages") or []}
            for row in normalized:
                existing[row["message_id"]] = row
            state["messages"] = list(existing.values())
            imports = list(state.get("imports") or [])
            imports.append(import_entry)
            state["imports"] = imports[-MAX_EXPORTS:]
            state = self._rebuild(state)
            self._append_history(
                state,
                action="communications_import",
                entity_type="import",
                entity_id=import_entry["import_id"],
                before=before,
                after=state,
                summary=f"Imported {import_entry['item_count']} communications records.",
            )
            self._save_state(state)
            return self.summary(state=state)

    def _state_view(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self._rebuild(self._load_state() if state is None else dict(state))
        messages = list(state.get("messages") or [])
        threads = list(state.get("threads") or [])
        schedule_history = list(state.get("schedule_history") or [])
        return {
            "status": "review_required" if state.get("completeness", {}).get("status") != "pass" else "pass",
            "schema_version": state.get("schema_version"),
            "matter_id": state.get("matter_id"),
            "generated_at": state.get("updated_at"),
            "message_count": len(messages),
            "thread_count": len(threads),
            "messages": [self._message_card(row) for row in messages],
            "threads": threads,
            "schedule_history": schedule_history,
            "parenting_time_events": list(state.get("parenting_time_events") or []),
            "agreements": list(state.get("agreements") or []),
            "claims": list(state.get("claims") or []),
            "completeness": dict(state.get("completeness") or {}),
            "review_history": list(state.get("history") or []),
            "imports": list(state.get("imports") or []),
            "exports": list(state.get("exports") or []),
            "review_required": True,
            "no_sentiment_or_fitness_inference": True,
            "no_parent_ranking": True,
            "no_abuse_conclusion": True,
        }

    def summary(self, *, state: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._state_view(state)

    def list_messages(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        state = self._state_view()
        rows = state["messages"][offset : offset + max(0, limit)]
        return {"status": state["status"], "count": len(rows), "total": state["message_count"], "messages": rows, "review_required": True}

    def list_threads(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        state = self._state_view()
        rows = state["threads"][offset : offset + max(0, limit)]
        return {"status": state["status"], "count": len(rows), "total": state["thread_count"], "threads": rows, "review_required": True}

    def schedule(self) -> dict[str, Any]:
        state = self._state_view()
        return {"status": state["status"], "count": len(state["schedule_history"]), "schedule_history": state["schedule_history"], "review_required": True}

    def parenting_time(self) -> dict[str, Any]:
        state = self._state_view()
        return {"status": state["status"], "count": len(state["parenting_time_events"]), "parenting_time_events": state["parenting_time_events"], "review_required": True}

    def agreements(self) -> dict[str, Any]:
        state = self._state_view()
        return {"status": state["status"], "count": len(state["agreements"]), "agreements": state["agreements"], "review_required": True}

    def claims(self) -> dict[str, Any]:
        state = self._state_view()
        return {"status": state["status"], "count": len(state["claims"]), "claims": state["claims"], "review_required": True}

    def completeness(self) -> dict[str, Any]:
        state = self._state_view()
        return {"status": state["completeness"].get("status", "review_required"), "completeness": state["completeness"], "review_required": True}

    def review_history(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        state = self._state_view()
        history = state["review_history"][offset : offset + max(0, limit)]
        return {"status": state["status"], "count": len(history), "history": history, "review_required": True}

    def export_bundle(self, *, format_name: str = "json") -> dict[str, Any]:
        format_name = _safe_text(format_name, limit=12).casefold()
        if format_name not in {"json", "txt"}:
            raise CommunicationsWorkbenchError("unsupported_export_format", "Unsupported communications export format.", status_code=400)
        with self._lock:
            state = self._state_view()
            export_id = _safe_id("export", _utc_now(), format_name, secrets.token_hex(4))
            export_dir = self.exports_dir / export_id
            export_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "export_id": export_id,
                "generated_at": _utc_now(),
                "matter_id": state["matter_id"],
                "schema_version": state["schema_version"],
                "format": format_name,
                "message_count": state["message_count"],
                "thread_count": state["thread_count"],
                "source_hash": _sha([message["source_hash"] for message in state["messages"]]),
                "thread_hash": _sha([thread["thread_key"] for thread in state["threads"]]),
                "review_history_hash": _sha(state["review_history"]),
                "review_required": True,
            }
            receipt = {
                "export_id": export_id,
                "export_sha256": _sha(payload),
                "bundle_sha256": _sha(state),
                "review_required": True,
            }
            json_path = export_dir / "communications-workbench-export.json"
            txt_path = export_dir / "communications-workbench-export.txt"
            receipt_path = export_dir / "communications-workbench-receipt.json"
            atomic_write_bytes(json_path, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
            atomic_write_bytes(txt_path, _export_text(state, payload, receipt).encode("utf-8"))
            atomic_write_bytes(receipt_path, json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8"))
            state = self._load_state()
            state = self._rebuild(state)
            exports = list(state.get("exports") or [])
            exports.append({**payload, **receipt, "export_dir": str(export_dir.name)})
            state["exports"] = exports[-MAX_EXPORTS:]
            self._append_history(
                state,
                action="communications_export",
                entity_type="export",
                entity_id=export_id,
                before=None,
                after=state,
                summary=f"Exported communications bundle in {format_name} format.",
            )
            self._save_state(state)
            return {
                "status": "review_required",
                "export_id": export_id,
                "export_dir": export_dir.name,
                "export_sha256": receipt["export_sha256"],
                "bundle_sha256": receipt["bundle_sha256"],
                "artifact_count": 3,
                "artifacts": [
                    CommunicationsArtifact("communications-workbench-export.json", f"{export_dir.name}/communications-workbench-export.json", _sha(payload), json_path.stat().st_size, "application/json").as_dict(),
                    CommunicationsArtifact("communications-workbench-export.txt", f"{export_dir.name}/communications-workbench-export.txt", _sha(_export_text(state, payload, receipt)), txt_path.stat().st_size, "text/plain").as_dict(),
                    CommunicationsArtifact("communications-workbench-receipt.json", f"{export_dir.name}/communications-workbench-receipt.json", _sha(receipt), receipt_path.stat().st_size, "application/json").as_dict(),
                ],
                "receipt": receipt,
                "payload": payload,
                "review_required": True,
            }


def _export_text(state: dict[str, Any], payload: dict[str, Any], receipt: dict[str, Any]) -> str:
    lines = [
        "# Communications and Parenting-Time Export",
        "",
        f"- Matter ID: `{state.get('matter_id')}`",
        f"- Export ID: `{payload.get('export_id')}`",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Message count: `{payload.get('message_count')}`",
        f"- Thread count: `{payload.get('thread_count')}`",
        f"- Export SHA-256: `{receipt.get('export_sha256')}`",
        f"- Bundle SHA-256: `{receipt.get('bundle_sha256')}`",
        "",
        "## Completeness",
        "",
        "```json",
        json.dumps(state.get("completeness") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Threads",
    ]
    for thread in state.get("threads") or []:
        lines.append(f"- {thread.get('thread_id')} :: {thread.get('subject')} ({thread.get('confidence')})")
    lines.extend(["", "## Schedule History"])
    for row in state.get("schedule_history") or []:
        lines.append(f"- {row.get('event_id')} :: {row.get('event_kind')} :: {row.get('status')}")
    return "\n".join(lines) + "\n"
