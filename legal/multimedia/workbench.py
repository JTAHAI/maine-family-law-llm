from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.data_boundaries.redaction import redact_private_identifiers
from legal.document_intelligence.privacy import deterministic_privacy_review
from legal.security.durable_io import atomic_write_bytes, durable_append_text
from legal.security.local_encryption import LocalEnvelopeEncryptor

SCHEMA_VERSION = "hearing_media_workbench_v1"
WORKSPACE_FOLDER = "23_HEARING_MEDIA_WORKBENCH"
MAX_MEDIA_RECORDS = 5_000
MAX_TRANSCRIPTS = 10_000
MAX_SEGMENTS = 100_000
MAX_TEXT = 100_000
MAX_EXPORTS = 500
MAX_HISTORY = 20_000
_LOCK = threading.RLock()
_MEDIA_KIND_RE = re.compile(r"^(audio|video)$", re.IGNORECASE)
_EXHIBIT_RE = re.compile(
    r"\b(?:exhibit|plaintiff's exhibit|defendant's exhibit|court exhibit)\s*([A-Za-z0-9]+)\b",
    re.IGNORECASE,
)
_TIMESTAMP_RE = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")
_CITATION_RE = re.compile(r"\[(?:cite|citation|source)\s*:\s*([^\]]+)\]", re.IGNORECASE)


class HearingMediaWorkbenchError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class HearingMediaArtifact:
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


def _safe_id(prefix: str, *parts: Any) -> str:
    payload = "\0".join(_safe_text(part, limit=1_000) for part in parts)
    return f"{prefix}-{_sha(payload)[:16]}"


def _ensure_list(value: Any, *, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _normalize_kind(value: Any) -> str:
    kind = _safe_text(value, limit=16).casefold()
    if not _MEDIA_KIND_RE.fullmatch(kind):
        raise HearingMediaWorkbenchError("unsupported_media_kind", "Only audio and video media are supported.", status_code=400)
    return kind


def _segment_text_span(text: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cursor = 0
    output: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        segment_text = _safe_text(segment.get("text"), limit=5_000)
        if not segment_text:
            continue
        start = text.find(segment_text, cursor)
        if start < 0:
            start = text.find(segment_text)
        if start < 0:
            start = cursor
        end = start + len(segment_text)
        cursor = end
        item = dict(segment)
        item["segment_id"] = _safe_text(item.get("segment_id") or f"segment-{index:04d}", limit=120)
        item["segment_index"] = index
        item["text_span"] = {"start": start, "end": end}
        item["text_sha256"] = _sha(segment_text)
        output.append(item)
    return output


def _parse_transcript_text(transcript_text: str) -> list[dict[str, Any]]:
    text = _safe_text(transcript_text, limit=MAX_TEXT * 5)
    if not text:
        return []
    raw_lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
    segments: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw_lines, start=1):
        speaker = "unknown"
        remainder = raw_line
        timestamp: str | None = None
        match = _TIMESTAMP_RE.search(raw_line)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            total = hours * 3600 + minutes * 60 + seconds
            timestamp = f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
        if raw_line.startswith("[") and "]" in raw_line:
            after_bracket = raw_line.split("]", 1)[1].strip()
            if ":" in after_bracket:
                prefix, suffix = after_bracket.split(":", 1)
                if prefix.strip():
                    speaker = prefix.strip()
                    remainder = suffix.strip()
        elif ":" in raw_line:
            prefix, suffix = raw_line.split(":", 1)
            if prefix.strip():
                remainder = suffix.strip()
                if "]" in prefix:
                    speaker = prefix.rsplit("]", 1)[-1].strip() or speaker
                else:
                    speaker = prefix.strip()
        elif "-" in raw_line and raw_line.lower().startswith("speaker"):
            prefix, suffix = raw_line.split("-", 1)
            speaker = prefix.strip()
            remainder = suffix.strip()
        segments.append(
            {
                "segment_id": f"segment-{index:04d}",
                "start_seconds": max(0, (index - 1) * 5),
                "end_seconds": max(0, index * 5),
                "timestamp": timestamp,
                "speaker_label": speaker,
                "speaker_label_source": "line_prefix" if speaker != "unknown" else "review_required",
                "text": remainder,
                "text_sha256": _sha(remainder),
                "review_status": "review_required",
                "no_biometric_identity_inference": True,
                "no_emotion_or_deception_inference": True,
            }
        )
    return _segment_text_span(transcript_text, segments)


def _classify_event(text: str) -> dict[str, Any]:
    lowered = f" {text.casefold()} "
    if any(term in lowered for term in ("opening", "call to order", "begin")):
        kind = "opening"
    elif any(term in lowered for term in ("objection", "sustained", "overruled")):
        kind = "objection"
    elif any(term in lowered for term in ("exhibit", "admitted", "marked")):
        kind = "exhibit_reference"
    elif any(term in lowered for term in ("witness", "testify", "examination", "cross")):
        kind = "witness_testimony"
    elif any(term in lowered for term in ("recess", "break")):
        kind = "recess"
    elif any(term in lowered for term in ("adjourn", "conclude", "close of hearing")):
        kind = "adjournment"
    elif any(term in lowered for term in ("ruling", "ordered", "order", "denied", "granted")):
        kind = "ruling"
    else:
        kind = "hearing_statement"
    return {
        "kind": kind,
        "no_emotion_or_deception_inference": True,
        "mention_does_not_prove_admission": True,
    }


def _append_history(action: str, entity_type: str, entity_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None, summary: str) -> dict[str, Any]:
    timestamp = datetime.now(UTC)
    return {
        "history_id": _safe_id("hist", action, entity_type, entity_id, secrets.token_hex(4), timestamp.isoformat()),
        "generated_at": _utc_now(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_sha256": _sha(before or {}),
        "after_sha256": _sha(after or {}),
        "summary": summary[:1_000],
        "review_required": True,
        "time_ns_hint": int(timestamp.timestamp() * 1_000_000_000),
    }


class HearingMediaWorkbenchStore:
    def __init__(self, case_root: Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.exists() or not self.case_root.is_dir():
            raise HearingMediaWorkbenchError("case_root_unavailable", "The active case workspace is unavailable.", status_code=409)
        self.root = self.case_root / WORKSPACE_FOLDER
        self.media_dir = self.root / "media"
        self.transcripts_dir = self.root / "transcripts"
        self.redactions_dir = self.root / "redactions"
        self.exports_dir = self.root / "exports"
        self.history_path = self.root / "hearing-media-history.jsonl"
        self.state_path = self.root / "hearing-media-workbench.json.enc"
        self._lock = threading.RLock()
        self._encryptor = LocalEnvelopeEncryptor(
            encryption_key or "hearing-media-local-development-key"
        )
        for folder in (self.root, self.media_dir, self.transcripts_dir, self.redactions_dir, self.exports_dir):
            if folder.exists() and folder.is_symlink():
                raise HearingMediaWorkbenchError("workspace_symlink_refused", "A hearing media workspace symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": self.case_root.name,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "engine_inventory": {
                "local_only": True,
                "automatic_download_blocked": True,
                "admitted_engine_available": False,
                "engine_status": "unavailable",
                "admitted_models": [],
                "review_required": True,
            },
            "media_records": [],
            "transcripts": [],
            "speaker_reviews": [],
            "timeline_builds": [],
            "exhibit_index": [],
            "citation_reviews": [],
            "privacy_reviews": [],
            "redacted_copies": [],
            "exports": [],
            "history": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return self._encryptor.decrypt_json(payload)
        except Exception as exc:  # pragma: no cover - defensive
            raise HearingMediaWorkbenchError("state_corrupt", "The hearing media workspace state is unavailable.", status_code=409) from exc

    def _save_state(self, state: dict[str, Any]) -> None:
        payload = dict(state)
        payload["updated_at"] = _utc_now()
        envelope = self._encryptor.encrypt_json(payload)
        atomic_write_bytes(self.state_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))

    def _record_history(self, state: dict[str, Any], entry: dict[str, Any]) -> None:
        history = _ensure_list(state.get("history"), limit=MAX_HISTORY)
        history.append(entry)
        state["history"] = history[:MAX_HISTORY]
        try:
            durable_append_text(self.history_path, json.dumps(entry, sort_keys=True) + "\n")
        except Exception:
            pass

    def _find_media(self, state: dict[str, Any], media_id: str) -> dict[str, Any]:
        for row in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS):
            if str(row.get("media_id") or "") == media_id:
                return dict(row)
        raise HearingMediaWorkbenchError("media_not_found", "The media item was not found.", status_code=404)

    def _find_transcript(self, state: dict[str, Any], transcript_id: str) -> dict[str, Any]:
        for row in _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS):
            if str(row.get("transcript_id") or "") == transcript_id:
                return dict(row)
        raise HearingMediaWorkbenchError("transcript_not_found", "The transcript was not found.", status_code=404)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            media_records = _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS)
            transcripts = _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS)
            redactions = _ensure_list(state.get("redacted_copies"), limit=MAX_EXPORTS)
            exports = _ensure_list(state.get("exports"), limit=MAX_EXPORTS)
            timeline_builds = _ensure_list(state.get("timeline_builds"), limit=MAX_EXPORTS)
            citations = _ensure_list(state.get("citation_reviews"), limit=MAX_EXPORTS)
            privacy_reviews = _ensure_list(state.get("privacy_reviews"), limit=MAX_EXPORTS)
            checklist_status = "pass" if media_records and transcripts and privacy_reviews else "review_required"
            return {
                "schema_version": SCHEMA_VERSION,
                "matter_id": state.get("matter_id", self.case_root.name),
                "updated_at": state.get("updated_at"),
                "review_required": True,
                "local_only": True,
                "no_cloud_transcription": True,
                "no_automatic_model_download": True,
                "engine_inventory": dict(state.get("engine_inventory") or {}),
                "media_count": len(media_records),
                "transcript_count": len(transcripts),
                "timeline_count": len(timeline_builds),
                "citation_count": len(citations),
                "privacy_review_count": len(privacy_reviews),
                "redaction_count": len(redactions),
                "export_count": len(exports),
                "appellate_record_status": checklist_status,
                "media_records": media_records,
                "transcripts": transcripts,
                "timeline_builds": timeline_builds,
                "exhibit_index": list(state.get("exhibit_index") or []),
                "citation_reviews": citations,
                "privacy_reviews": privacy_reviews,
                "redacted_copies": redactions,
                "exports": exports,
                "history": list(state.get("history") or []),
            }

    def import_media(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            records = _ensure_list(payload.get("media") or payload.get("media_items"), limit=MAX_MEDIA_RECORDS)
            if not records:
                raise HearingMediaWorkbenchError("media_required", "At least one media item is required.", status_code=400)
            imported: list[dict[str, Any]] = []
            for raw in records:
                if not isinstance(raw, dict):
                    continue
                media_id = _safe_text(raw.get("media_id") or raw.get("source_id") or raw.get("filename"), limit=120)
                if not media_id:
                    raise HearingMediaWorkbenchError("media_id_required", "Each media item requires a media_id.", status_code=400)
                kind = _normalize_kind(raw.get("media_kind") or raw.get("kind") or raw.get("source_type"))
                source_hash = _safe_text(raw.get("source_hash") or raw.get("sha256"), limit=64).casefold()
                if source_hash and not re.fullmatch(r"[a-f0-9]{64}", source_hash):
                    raise HearingMediaWorkbenchError("source_hash_invalid", "The source hash must be a SHA-256 hex digest.", status_code=400)
                duplicate_group = source_hash or _sha({"title": raw.get("title"), "kind": kind})[:16]
                row = {
                    "media_id": media_id,
                    "title": _safe_text(raw.get("title") or raw.get("filename") or media_id, limit=240),
                    "media_kind": kind,
                    "filename": _safe_text(raw.get("filename") or raw.get("source_locator") or media_id, limit=240),
                    "source_hash": source_hash,
                    "duplicate_group": duplicate_group,
                    "duration_seconds": max(0, int(raw.get("duration_seconds") or 0)),
                    "recorded_at": _safe_text(raw.get("recorded_at") or raw.get("date") or "", limit=80) or "unknown",
                    "confidentiality": _safe_text(raw.get("confidentiality") or "private_record", limit=80),
                    "notes": _safe_text(raw.get("notes") or "", limit=1_000),
                    "imported_at": _utc_now(),
                    "transcription_status": "not_run",
                    "transcript_count": 0,
                    "speaker_review_status": "not_run",
                    "privacy_review_status": "not_run",
                    "no_biometric_identity_inference": True,
                    "no_emotion_or_deception_inference": True,
                    "review_required": True,
                }
                imported.append(row)
            existing = [dict(row) for row in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS)]
            existing_ids = {str(row.get("media_id") or "") for row in existing}
            for row in imported:
                if row["media_id"] in existing_ids:
                    raise HearingMediaWorkbenchError("media_id_conflict", "The media item already exists.", status_code=409)
                existing.append(row)
                existing_ids.add(row["media_id"])
            state["media_records"] = existing[:MAX_MEDIA_RECORDS]
            history = _append_history("import_media", "media", ",".join(row["media_id"] for row in imported), None, {"imported": imported}, f"Imported {len(imported)} media item(s).")
            self._record_history(state, history)
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "imported_count": len(imported),
                "media_records": imported,
                "duplicate_groups": sorted({row["duplicate_group"] for row in imported}),
                "no_original_modified": True,
                "engine_inventory": dict(state.get("engine_inventory") or {}),
            }

    def media(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            record = self._find_media(state, media_id)
            return {"status": "pass", "review_required": True, "media": record}

    def transcribe_media(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            media = self._find_media(state, media_id)
            transcript_text = _safe_text(payload.get("transcript_text") or payload.get("text"), limit=MAX_TEXT * 5)
            if not transcript_text:
                return {
                    "status": "blocked",
                    "blockers": ["no_admitted_transcription_engine"],
                    "review_required": True,
                    "media_id": media_id,
                    "engine_inventory": dict(state.get("engine_inventory") or {}),
                    "transcription_status": "not_run",
                    "no_automatic_model_download": True,
                }
            provided_segments = _ensure_list(payload.get("segments"), limit=MAX_SEGMENTS)
            if provided_segments:
                segments = _segment_text_span(transcript_text, [dict(segment) for segment in provided_segments if isinstance(segment, dict)])
            else:
                segments = _parse_transcript_text(transcript_text)
            transcript_id = _safe_id("transcript", media_id, transcript_text, _utc_now())
            transcript_row = {
                "transcript_id": transcript_id,
                "media_id": media_id,
                "media_hash": media.get("source_hash", ""),
                "transcript_kind": _safe_text(payload.get("transcript_kind") or "derived", limit=80),
                "transcript_text": transcript_text,
                "transcript_sha256": _sha(transcript_text),
                "segment_count": len(segments),
                "segments": segments,
                "speaker_policy": "manual_local_labels_only",
                "no_biometric_identity_inference": True,
                "no_emotion_or_deception_inference": True,
                "source_span_policy": "exact_char_spans",
                "transcription_method": "manual_synthetic" if not payload.get("engine_id") else "local_engine",
                "transcription_status": "pass",
                "review_required": True,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
            transcripts = [dict(row) for row in _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS)]
            transcripts.append(transcript_row)
            state["transcripts"] = transcripts[:MAX_TRANSCRIPTS]
            media["transcription_status"] = "pass"
            media["transcript_count"] = int(media.get("transcript_count") or 0) + 1
            media["transcript_id"] = transcript_id
            media["updated_at"] = _utc_now()
            state["media_records"] = [media if str(row.get("media_id") or "") == media_id else dict(row) for row in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS)]
            transcript_dir = self.transcripts_dir / media_id / transcript_id
            transcript_dir.mkdir(parents=True, exist_ok=True)
            text_path = transcript_dir / "transcript.txt"
            json_path = transcript_dir / "transcript.json"
            receipt_path = transcript_dir / "transcript-receipt.json"
            text_path.write_text(transcript_text, encoding="utf-8")
            transcript_payload = {
                "schema_version": SCHEMA_VERSION,
                "transcript": transcript_row,
                "media_hash": media.get("source_hash", ""),
                "transcript_sha256": transcript_row["transcript_sha256"],
                "no_original_modified": True,
                "review_required": True,
            }
            json_path.write_text(json.dumps(transcript_payload, indent=2, sort_keys=True), encoding="utf-8")
            receipt = {
                "schema_version": "hearing_media_transcript_receipt_v1",
                "media_id": media_id,
                "transcript_id": transcript_id,
                "transcript_sha256": transcript_row["transcript_sha256"],
                "segment_count": len(segments),
                "generated_at": _utc_now(),
                "review_required": True,
            }
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
            artifacts = [
                HearingMediaArtifact("transcript.txt", f"{WORKSPACE_FOLDER}/transcripts/{media_id}/{transcript_id}/transcript.txt", _sha(text_path.read_bytes()), text_path.stat().st_size, "text/plain"),
                HearingMediaArtifact("transcript.json", f"{WORKSPACE_FOLDER}/transcripts/{media_id}/{transcript_id}/transcript.json", _sha(json_path.read_bytes()), json_path.stat().st_size, "application/json"),
                HearingMediaArtifact("transcript-receipt.json", f"{WORKSPACE_FOLDER}/transcripts/{media_id}/{transcript_id}/transcript-receipt.json", _sha(receipt_path.read_bytes()), receipt_path.stat().st_size, "application/json"),
            ]
            history = _append_history("transcribe_media", "transcript", transcript_id, None, transcript_row, f"Created a transcript for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "media_id": media_id,
                "transcript": transcript_row,
                "artifacts": [artifact.as_dict() for artifact in artifacts],
                "no_original_modified": True,
                "no_cloud_transcription": True,
                "no_automatic_model_download": True,
            }

    def _transcript_for_media(self, state: dict[str, Any], media_id: str) -> dict[str, Any]:
        transcripts = [dict(row) for row in _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS) if str(row.get("media_id") or "") == media_id]
        if not transcripts:
            raise HearingMediaWorkbenchError("transcript_not_found", "A transcript has not been created for this media item.", status_code=404)
        return transcripts[-1]

    def speaker_review(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            updates = _ensure_list(payload.get("labels") or payload.get("segment_updates"), limit=MAX_SEGMENTS)
            if not updates:
                raise HearingMediaWorkbenchError("speaker_labels_required", "Speaker labels are required.", status_code=400)
            segments = [dict(segment) for segment in transcript.get("segments") or []]
            by_id = {str(segment.get("segment_id") or ""): segment for segment in segments}
            changes: list[dict[str, Any]] = []
            for raw in updates:
                if not isinstance(raw, dict):
                    continue
                segment_id = _safe_text(raw.get("segment_id"), limit=120)
                if not segment_id or segment_id not in by_id:
                    continue
                segment = by_id[segment_id]
                before = str(segment.get("speaker_label") or "unknown")
                after = _safe_text(raw.get("speaker_label") or raw.get("label"), limit=120) or before
                segment["speaker_label"] = after
                segment["speaker_label_source"] = "user_review"
                segment["speaker_reviewed_at"] = _utc_now()
                changes.append({
                    "segment_id": segment_id,
                    "before": before,
                    "after": after,
                    "speaker_identity_inference_blocked": True,
                    "review_required": True,
                })
            transcript["segments"] = segments
            transcript["updated_at"] = _utc_now()
            transcript["speaker_review_status"] = "reviewed"
            transcript["speaker_review_history"] = changes
            transcripts = [transcript if str(row.get("transcript_id") or "") == transcript["transcript_id"] else dict(row) for row in _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS)]
            state["transcripts"] = transcripts
            state["speaker_reviews"] = list(_ensure_list(state.get("speaker_reviews"), limit=MAX_HISTORY)) + [{"media_id": media_id, "transcript_id": transcript["transcript_id"], "changes": changes, "reviewed_at": _utc_now()}]
            history = _append_history("speaker_review", "transcript", transcript["transcript_id"], None, transcript, f"Reviewed speaker labels for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "media_id": media_id,
                "transcript": transcript,
                "changes": changes,
                "speaker_identity_inference_blocked": True,
                "no_biometric_identity_inference": True,
            }

    def build_timeline(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            events: list[dict[str, Any]] = []
            for segment in transcript.get("segments") or []:
                text = _safe_text(segment.get("text"), limit=5_000)
                if not text:
                    continue
                classification = _classify_event(text)
                event = {
                    "event_id": _safe_id("event", media_id, segment.get("segment_id"), text),
                    "media_id": media_id,
                    "transcript_id": transcript["transcript_id"],
                    "segment_id": segment.get("segment_id"),
                    "start_seconds": segment.get("start_seconds"),
                    "end_seconds": segment.get("end_seconds"),
                    "timestamp_start": segment.get("timestamp") or f"{int(segment.get('start_seconds') or 0):02d}:00:00",
                    "timestamp_end": f"{int(segment.get('end_seconds') or 0):02d}:00:00",
                    "text": text,
                    "speaker_label": segment.get("speaker_label") or "unknown",
                    "classification": classification,
                    "source_span": dict(segment.get("text_span") or {}),
                    "review_required": True,
                    "no_emotion_or_deception_inference": True,
                }
                events.append(event)
            events.sort(key=lambda row: (int(row.get("start_seconds") or 0), str(row.get("event_id") or "")))
            build = {
                "timeline_id": _safe_id("timeline", media_id, transcript["transcript_id"], len(events)),
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "generated_at": _utc_now(),
                "event_count": len(events),
                "events": events,
                "review_required": True,
                "exact_timestamp_required": True,
            }
            builds = [dict(row) for row in _ensure_list(state.get("timeline_builds"), limit=MAX_EXPORTS)]
            builds.append(build)
            state["timeline_builds"] = builds[:MAX_EXPORTS]
            history = _append_history("build_timeline", "timeline", build["timeline_id"], None, build, f"Built a hearing timeline for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "timeline": build}

    def compare_transcripts(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            official_text = _safe_text(payload.get("official_transcript_text") or payload.get("official_text"), limit=MAX_TEXT * 5)
            if not official_text:
                raise HearingMediaWorkbenchError("official_transcript_required", "An official transcript is required for comparison.", status_code=400)
            derived_text = _safe_text(payload.get("derived_transcript_text") or transcript.get("transcript_text"), limit=MAX_TEXT * 5)
            official_lines = [line.strip() for line in official_text.splitlines() if line.strip()]
            derived_lines = [line.strip() for line in derived_text.splitlines() if line.strip()]
            rows: list[dict[str, Any]] = []
            for index in range(max(len(official_lines), len(derived_lines))):
                official = official_lines[index] if index < len(official_lines) else ""
                derived = derived_lines[index] if index < len(derived_lines) else ""
                status = "match" if official == derived else ("missing" if official and not derived else "extra" if derived and not official else "changed")
                rows.append(
                    {
                        "line_number": index + 1,
                        "official_text": official,
                        "derived_text": derived,
                        "status": status,
                        "review_required": True,
                    }
                )
            comparison = {
                "comparison_id": _safe_id("comparison", media_id, transcript["transcript_id"], official_text),
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "official_transcript_sha256": _sha(official_text),
                "derived_transcript_sha256": _sha(derived_text),
                "line_count": len(rows),
                "rows": rows,
                "review_required": True,
                "no_official_transcript_equivalence_inference": True,
            }
            history = _append_history("compare_transcripts", "comparison", comparison["comparison_id"], None, comparison, f"Compared official and derived transcripts for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "comparison": comparison}

    def exhibit_references(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            text = transcript.get("transcript_text") or ""
            matches = []
            for match in _EXHIBIT_RE.finditer(text):
                exhibit_code = _safe_text(match.group(1), limit=40)
                matches.append(
                    {
                        "exhibit_id": f"exhibit-{exhibit_code.casefold()}",
                        "label": exhibit_code,
                        "status": "mentioned",
                        "mention_span": {"start": match.start(), "end": match.end()},
                        "source_transcript_id": transcript["transcript_id"],
                        "review_required": True,
                        "mention_does_not_prove_admission": True,
                    }
                )
            exhibit_index = {
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "exhibit_count": len(matches),
                "exhibits": matches,
                "review_required": True,
                "mention_does_not_prove_admission": True,
            }
            state["exhibit_index"] = matches
            history = _append_history("exhibit_references", "exhibit_index", media_id, None, exhibit_index, f"Built exhibit references for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "exhibit_index": exhibit_index}

    def appellate_record_completeness(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            privacy = next((row for row in reversed(_ensure_list(state.get("privacy_reviews"), limit=MAX_EXPORTS)) if row.get("media_id") == media_id), {})
            redactions = [row for row in _ensure_list(state.get("redacted_copies"), limit=MAX_EXPORTS) if row.get("media_id") == media_id]
            citation_review = next((row for row in reversed(_ensure_list(state.get("citation_reviews"), limit=MAX_EXPORTS)) if row.get("media_id") == media_id), {})
            checklist = [
                {"item": "original media hash", "status": "present" if _find_media_exists(state, media_id) else "missing"},
                {"item": "derived transcript", "status": "present" if transcript else "missing"},
                {"item": "speaker review", "status": "present" if transcript.get("speaker_review_status") == "reviewed" else "missing"},
                {"item": "timeline build", "status": "present" if any(build.get("media_id") == media_id for build in _ensure_list(state.get("timeline_builds"), limit=MAX_EXPORTS)) else "missing"},
                {"item": "exhibit references", "status": "present" if state.get("exhibit_index") else "missing"},
                {"item": "privacy review", "status": "present" if privacy else "missing"},
                {"item": "redacted derivative", "status": "present" if redactions else "missing"},
                {
                    "item": "citation verification",
                    "status": "present"
                    if citation_review and int(citation_review.get("unresolved_count") or 0) == 0
                    else ("blocked" if citation_review else "missing"),
                },
            ]
            missing = [row for row in checklist if row["status"] != "present"]
            status = "pass" if not missing else "review_required"
            return {
                "status": status,
                "review_required": True,
                "media_id": media_id,
                "checklist": checklist,
                "missing": missing,
                "original_media_unchanged": True,
                "no_biometric_identity_inference": True,
                "no_emotion_or_deception_inference": True,
            }

    def record_citations(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            raw_citations = _ensure_list(payload.get("citations"), limit=MAX_SEGMENTS)
            citations: list[dict[str, Any]] = []
            unresolved: list[dict[str, Any]] = []
            for raw in raw_citations:
                if not isinstance(raw, dict):
                    continue
                label = _safe_text(raw.get("label") or raw.get("citation") or raw.get("text"), limit=160)
                span = raw.get("source_span")
                resolved = isinstance(span, dict) and isinstance(span.get("start"), int) and isinstance(span.get("end"), int)
                row = {
                    "citation_id": _safe_id("cite", media_id, label, json.dumps(span, sort_keys=True, default=str)),
                    "media_id": media_id,
                    "transcript_id": transcript["transcript_id"],
                    "label": label,
                    "source_span": span if resolved else None,
                    "status": "resolved" if resolved else "unresolved",
                    "review_required": True,
                    "does_not_verify_substantive_truth": True,
                }
                citations.append(row)
                if not resolved:
                    unresolved.append(row)
            citation_review = {
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "citation_count": len(citations),
                "resolved_count": len(citations) - len(unresolved),
                "unresolved_count": len(unresolved),
                "citations": citations,
                "status": "blocked" if unresolved else "pass",
                "review_required": True,
                "citation_resolution_blocked": bool(unresolved),
            }
            reviews = [dict(row) for row in _ensure_list(state.get("citation_reviews"), limit=MAX_EXPORTS)]
            reviews.append(citation_review)
            state["citation_reviews"] = reviews[:MAX_EXPORTS]
            history = _append_history("record_citations", "citation_review", media_id, None, citation_review, f"Recorded {len(citations)} citation row(s) for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass" if not unresolved else "blocked", "review_required": True, "citation_review": citation_review}

    def privacy_scan(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            review = deterministic_privacy_review(transcript.get("transcript_text") or "")
            redacted_text = redact_private_identifiers(transcript.get("transcript_text") or "").text
            privacy_review = {
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "privacy_review": review,
                "redacted_preview_sha256": _sha(redacted_text),
                "review_required": True,
                "local_only": True,
                "no_biometric_identity_inference": True,
                "no_emotion_or_deception_inference": True,
            }
            reviews = [dict(row) for row in _ensure_list(state.get("privacy_reviews"), limit=MAX_EXPORTS)]
            reviews.append(privacy_review)
            state["privacy_reviews"] = reviews[:MAX_EXPORTS]
            history = _append_history("privacy_scan", "privacy_review", media_id, None, privacy_review, f"Ran a privacy scan for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "privacy_review": privacy_review}

    def redacted_copy(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            approved = bool(payload.get("approved"))
            if not approved:
                raise HearingMediaWorkbenchError("redaction_consent_required", "Explicit approval is required before creating a redacted copy.", status_code=409)
            source_hash = _safe_text(payload.get("source_hash") or transcript.get("transcript_sha256") or "", limit=64).casefold()
            if source_hash and source_hash != transcript.get("transcript_sha256"):
                raise HearingMediaWorkbenchError("transcript_hash_mismatch", "The source transcript hash changed before redaction.", status_code=409)
            redacted_text = redact_private_identifiers(transcript.get("transcript_text") or "").text
            redacted_dir = self.redactions_dir / media_id / transcript["transcript_id"]
            redacted_dir.mkdir(parents=True, exist_ok=True)
            txt_path = redacted_dir / "redacted-transcript.txt"
            json_path = redacted_dir / "redacted-transcript.json"
            receipt_path = redacted_dir / "redaction-receipt.json"
            txt_path.write_text(redacted_text, encoding="utf-8")
            body = {
                "schema_version": SCHEMA_VERSION,
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "original_transcript_sha256": transcript["transcript_sha256"],
                "redacted_transcript_sha256": _sha(redacted_text),
                "review_required": True,
                "no_original_modified": True,
            }
            json_path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
            receipt = {
                "schema_version": "hearing_media_redaction_receipt_v1",
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "redacted_transcript_sha256": _sha(redacted_text),
                "generated_at": _utc_now(),
                "review_required": True,
            }
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
            artifacts = [
                HearingMediaArtifact("redacted-transcript.txt", f"{WORKSPACE_FOLDER}/redactions/{media_id}/{transcript['transcript_id']}/redacted-transcript.txt", _sha(txt_path.read_bytes()), txt_path.stat().st_size, "text/plain"),
                HearingMediaArtifact("redacted-transcript.json", f"{WORKSPACE_FOLDER}/redactions/{media_id}/{transcript['transcript_id']}/redacted-transcript.json", _sha(json_path.read_bytes()), json_path.stat().st_size, "application/json"),
                HearingMediaArtifact("redaction-receipt.json", f"{WORKSPACE_FOLDER}/redactions/{media_id}/{transcript['transcript_id']}/redaction-receipt.json", _sha(receipt_path.read_bytes()), receipt_path.stat().st_size, "application/json"),
            ]
            row = {
                "media_id": media_id,
                "transcript_id": transcript["transcript_id"],
                "redacted_transcript_sha256": _sha(redacted_text),
                "original_transcript_sha256": transcript["transcript_sha256"],
                "review_required": True,
                "no_original_modified": True,
            }
            redactions = [dict(item) for item in _ensure_list(state.get("redacted_copies"), limit=MAX_EXPORTS)]
            redactions.append(row)
            state["redacted_copies"] = redactions[:MAX_EXPORTS]
            history = _append_history("redacted_copy", "redaction", media_id, None, row, f"Created a redacted copy for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "media_id": media_id,
                "artifacts": [artifact.as_dict() for artifact in artifacts],
                "redacted_copy": row,
                "no_original_modified": True,
            }

    def review_history(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            rows = list(_ensure_list(state.get("history"), limit=MAX_HISTORY))
            sliced = rows[offset : offset + limit]
            return {"status": "pass", "review_required": True, "history": sliced, "total": len(rows), "offset": offset, "limit": limit}

    def cancel_transcription(self, media_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            media = self._find_media(state, media_id)
            media["transcription_status"] = "cancelled"
            media["updated_at"] = _utc_now()
            state["media_records"] = [media if str(row.get("media_id") or "") == media_id else dict(row) for row in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS)]
            row = {"media_id": media_id, "status": "cancelled", "review_required": True, "no_cloud_transcription": True}
            history = _append_history("cancel_transcription", "media", media_id, None, row, f"Cancelled transcription for media {media_id}.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "cancellation": row}

    def export_bundle(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            if not _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS):
                raise HearingMediaWorkbenchError("media_required", "At least one media item is required before export.", status_code=400)
            unresolved_citations: list[dict[str, Any]] = []
            latest_by_media: dict[str, dict[str, Any]] = {}
            for row in reversed(_ensure_list(state.get("citation_reviews"), limit=MAX_EXPORTS)):
                media_key = str(row.get("media_id") or "")
                if media_key and media_key not in latest_by_media:
                    latest_by_media[media_key] = dict(row)
            for media in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS):
                media_key = str(media.get("media_id") or "")
                review = latest_by_media.get(media_key)
                if review and int(review.get("unresolved_count") or 0) > 0:
                    unresolved_citations.append(review)
            if unresolved_citations:
                return {
                    "status": "blocked",
                    "blockers": ["unresolved_citations_present"],
                    "review_required": True,
                    "unresolved_citations": unresolved_citations,
                    "no_original_modified": True,
                }
            bundle_kind = _safe_text((payload or {}).get("export_kind") or "hearing_media_review_bundle", limit=80)
            build_id = _safe_id("hearing-media", self.case_root.name, _utc_now(), bundle_kind)
            export_dir = self.exports_dir / build_id
            export_dir.mkdir(parents=True, exist_ok=True)
            summary = self.summary()
            bundle = {
                "schema_version": SCHEMA_VERSION,
                "build_id": build_id,
                "export_kind": bundle_kind,
                "generated_at": _utc_now(),
                "summary": summary,
                "review_required": True,
                "no_original_modified": True,
            }
            txt_lines = [
                "Hearing media workbench export",
                f"Build ID: {build_id}",
                f"Matter: {summary['matter_id']}",
                f"Media count: {summary['media_count']}",
                f"Transcript count: {summary['transcript_count']}",
                f"Timeline count: {summary['timeline_count']}",
                f"Privacy review count: {summary['privacy_review_count']}",
                f"Redaction count: {summary['redaction_count']}",
            ]
            json_path = export_dir / "hearing-media-workbench-export.json"
            txt_path = export_dir / "hearing-media-workbench-export.txt"
            receipt_path = export_dir / "hearing-media-workbench-receipt.json"
            json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
            txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
            receipt = {
                "schema_version": "hearing_media_export_receipt_v1",
                "build_id": build_id,
                "export_kind": bundle_kind,
                "bundle_sha256": _sha(bundle),
                "export_sha256": _sha(txt_path.read_bytes()),
                "generated_at": _utc_now(),
                "review_required": True,
            }
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
            artifacts = [
                HearingMediaArtifact("hearing-media-workbench-export.json", f"{WORKSPACE_FOLDER}/exports/{build_id}/hearing-media-workbench-export.json", _sha(json_path.read_bytes()), json_path.stat().st_size, "application/json"),
                HearingMediaArtifact("hearing-media-workbench-export.txt", f"{WORKSPACE_FOLDER}/exports/{build_id}/hearing-media-workbench-export.txt", _sha(txt_path.read_bytes()), txt_path.stat().st_size, "text/plain"),
                HearingMediaArtifact("hearing-media-workbench-receipt.json", f"{WORKSPACE_FOLDER}/exports/{build_id}/hearing-media-workbench-receipt.json", _sha(receipt_path.read_bytes()), receipt_path.stat().st_size, "application/json"),
            ]
            exports = [dict(row) for row in _ensure_list(state.get("exports"), limit=MAX_EXPORTS)]
            exports.append({"build_id": build_id, "bundle_sha256": receipt["bundle_sha256"], "export_kind": bundle_kind, "review_required": True})
            state["exports"] = exports[:MAX_EXPORTS]
            history = _append_history("export_bundle", "export", build_id, None, bundle, f"Exported a hearing media review bundle ({bundle_kind}).")
            self._record_history(state, history)
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "build_id": build_id,
                "bundle": bundle,
                "receipt": receipt,
                "artifacts": [artifact.as_dict() for artifact in artifacts],
            }


def _find_media_exists(state: dict[str, Any], media_id: str) -> bool:
    for row in _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS):
        if str(row.get("media_id") or "") == media_id:
            return True
    return False
