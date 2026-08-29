from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import threading
import wave
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
MAX_KEYFRAME_REVIEWS = 2_000
MAX_KEYFRAMES_PER_REVIEW = 24
MAX_KEYFRAME_BYTES = 4 * 1024 * 1024
MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
MAX_REDACTION_DERIVATIVE_BYTES = 32 * 1024 * 1024
MAX_REDACTION_INTERVALS = 100
MAX_COURTROOM_SESSIONS = 2_000
MAX_PRIVATE_NOTES = 5_000
MAX_PLAYBACK_PREVIEW_BYTES = 32 * 1024 * 1024
_LOCK = threading.RLock()
_MEDIA_KIND_RE = re.compile(r"^(audio|video|image)$", re.IGNORECASE)
_EXHIBIT_RE = re.compile(
    r"\b(?:exhibit|plaintiff's exhibit|defendant's exhibit|court exhibit)\s*([A-Za-z0-9]+)\b",
    re.IGNORECASE,
)
_TIMESTAMP_RE = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")
_CITATION_RE = re.compile(r"\[(?:cite|citation|source)\s*:\s*([^\]]+)\]", re.IGNORECASE)
_SAFE_WORK_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,119}\Z")


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


def _safe_work_id(value: Any, *, field: str) -> str:
    result = _safe_text(value, limit=120)
    if not _SAFE_WORK_ID_RE.fullmatch(result):
        raise HearingMediaWorkbenchError(f"{field}_invalid", f"Use a safe {field.replace('_', ' ')} with letters, numbers, underscores, or hyphens.", status_code=400)
    return result


def _ensure_list(value: Any, *, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _normalize_kind(value: Any) -> str:
    kind = _safe_text(value, limit=16).casefold()
    if not _MEDIA_KIND_RE.fullmatch(kind):
        raise HearingMediaWorkbenchError("unsupported_media_kind", "Only audio, video, and image media are supported.", status_code=400)
    return kind


def _sha256_file(path: Path, *, max_bytes: int = MAX_VIDEO_BYTES) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HearingMediaWorkbenchError("media_source_unavailable", "The selected local media file is unavailable.", status_code=404) from exc
    if size < 1 or size > max_bytes:
        raise HearingMediaWorkbenchError("media_source_size_blocked", "The selected local media file is empty or exceeds the local review limit.", status_code=413)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise HearingMediaWorkbenchError("media_source_unavailable", "The selected local media file is unavailable.", status_code=404) from exc
    return digest.hexdigest()


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
        self.keyframes_dir = self.root / "keyframes"
        self.media_redactions_dir = self.root / "media-redactions"
        self.redactions_dir = self.root / "redactions"
        self.courtroom_notes_dir = self.root / "courtroom-notes"
        self.exports_dir = self.root / "exports"
        self.history_path = self.root / "hearing-media-history.jsonl"
        self.state_path = self.root / "hearing-media-workbench.json.enc"
        self._lock = threading.RLock()
        self._encryptor = LocalEnvelopeEncryptor(
            encryption_key or "hearing-media-local-development-key"
        )
        for folder in (self.root, self.media_dir, self.transcripts_dir, self.keyframes_dir, self.media_redactions_dir, self.redactions_dir, self.courtroom_notes_dir, self.exports_dir):
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
            "keyframe_reviews": [],
            "media_redaction_derivatives": [],
            "screenshot_conversations": [],
            "metadata_inspections": [],
            "timeline_builds": [],
            "exhibit_index": [],
            "citation_reviews": [],
            "privacy_reviews": [],
            "redacted_copies": [],
            "courtroom_sessions": [],
            "exports": [],
            "history": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = self._encryptor.decrypt_json(payload)
            # New review-only media work product is additive.  Existing matters
            # keep their original media and transcript state unchanged.
            state.setdefault("courtroom_sessions", [])
            return state
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

    def _local_media_source(self, relative_file: Any, *, allowed_suffixes: set[str], media_label: str) -> Path:
        value = _safe_text(relative_file, limit=512)
        if not value:
            raise HearingMediaWorkbenchError("media_source_required", f"Choose a local {media_label} file inside the active matter.", status_code=400)
        candidate = Path(value)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise HearingMediaWorkbenchError("media_source_path_refused", f"Choose a relative local {media_label} file inside the active matter.", status_code=400)
        raw_path = self.case_root.joinpath(candidate)
        path_part = self.case_root
        for part in candidate.parts:
            path_part = path_part / part
            if path_part.is_symlink():
                raise HearingMediaWorkbenchError("media_source_path_refused", f"The selected {media_label} cannot traverse a symlink.", status_code=400)
        try:
            resolved = raw_path.resolve(strict=True)
            resolved.relative_to(self.case_root)
        except (OSError, ValueError) as exc:
            raise HearingMediaWorkbenchError("media_source_path_refused", f"The selected {media_label} is outside the active matter or unavailable.", status_code=400) from exc
        if raw_path.is_symlink() or not resolved.is_file():
            raise HearingMediaWorkbenchError("media_source_path_refused", f"The selected {media_label} must be a regular local file.", status_code=400)
        if resolved.suffix.casefold() not in allowed_suffixes:
            raise HearingMediaWorkbenchError("media_source_type_blocked", f"The selected local file is not an allowed {media_label} type.", status_code=415)
        return resolved

    def _local_video_source(self, relative_file: Any) -> Path:
        return self._local_media_source(relative_file, allowed_suffixes={".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}, media_label="video")

    def _local_audio_source(self, relative_file: Any) -> Path:
        return self._local_media_source(relative_file, allowed_suffixes={".wav"}, media_label="WAV audio")

    def _local_image_source(self, relative_file: Any) -> Path:
        return self._local_media_source(relative_file, allowed_suffixes={".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}, media_label="image")

    def _local_playback_source(self, media: dict[str, Any], relative_file: Any) -> Path:
        kind = str(media.get("media_kind") or "").casefold()
        if kind == "audio":
            return self._local_audio_source(relative_file)
        if kind == "video":
            return self._local_video_source(relative_file)
        raise HearingMediaWorkbenchError("playable_media_required", "Courtroom playback is available only for imported audio or video.", status_code=400)

    @staticmethod
    def _playback_media_type(path: Path, media_kind: str) -> str:
        suffix = path.suffix.casefold()
        if media_kind == "audio" and suffix == ".wav":
            return "audio/wav"
        return {
            ".avi": "video/x-msvideo",
            ".m4v": "video/x-m4v",
            ".mkv": "video/x-matroska",
            ".mov": "video/quicktime",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
        }.get(suffix, "application/octet-stream")

    def _keyframe_review(self, state: dict[str, Any], media_id: str, review_id: str) -> dict[str, Any]:
        for row in _ensure_list(state.get("keyframe_reviews"), limit=MAX_KEYFRAME_REVIEWS):
            if str(row.get("review_id") or "") == review_id and str(row.get("media_id") or "") == media_id:
                return dict(row)
        raise HearingMediaWorkbenchError("keyframe_review_not_found", "The selected keyframe review was not found in this matter.", status_code=404)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            media_records = _ensure_list(state.get("media_records"), limit=MAX_MEDIA_RECORDS)
            transcripts = _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS)
            keyframe_reviews = _ensure_list(state.get("keyframe_reviews"), limit=MAX_KEYFRAME_REVIEWS)
            media_redactions = _ensure_list(state.get("media_redaction_derivatives"), limit=MAX_EXPORTS)
            screenshot_conversations = _ensure_list(state.get("screenshot_conversations"), limit=MAX_EXPORTS)
            metadata_inspections = _ensure_list(state.get("metadata_inspections"), limit=MAX_EXPORTS)
            redactions = _ensure_list(state.get("redacted_copies"), limit=MAX_EXPORTS)
            exports = _ensure_list(state.get("exports"), limit=MAX_EXPORTS)
            timeline_builds = _ensure_list(state.get("timeline_builds"), limit=MAX_EXPORTS)
            courtroom_sessions = _ensure_list(state.get("courtroom_sessions"), limit=MAX_COURTROOM_SESSIONS)
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
                "keyframe_review_count": len(keyframe_reviews),
                "media_redaction_derivative_count": len(media_redactions),
                "screenshot_conversation_count": len(screenshot_conversations),
                "metadata_inspection_count": len(metadata_inspections),
                "timeline_count": len(timeline_builds),
                "courtroom_session_count": len(courtroom_sessions),
                "citation_count": len(citations),
                "privacy_review_count": len(privacy_reviews),
                "redaction_count": len(redactions),
                "export_count": len(exports),
                "appellate_record_status": checklist_status,
                "media_records": media_records,
                "transcripts": transcripts,
                "keyframe_reviews": keyframe_reviews,
                "media_redaction_derivatives": media_redactions,
                "screenshot_conversations": screenshot_conversations,
                "metadata_inspections": metadata_inspections,
                "timeline_builds": timeline_builds,
                "courtroom_sessions": [
                    {
                        key: row.get(key)
                        for key in (
                            "session_id",
                            "media_id",
                            "media_hash",
                            "clip_start_seconds",
                            "clip_end_seconds",
                            "transcript_id",
                            "created_at",
                            "review_required",
                            "private_notes_separate",
                        )
                    }
                    for row in courtroom_sessions
                ],
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

    @staticmethod
    def _courtroom_session(state: dict[str, Any], session_id: str) -> dict[str, Any]:
        safe_session_id = _safe_work_id(session_id, field="session_id")
        for row in _ensure_list(state.get("courtroom_sessions"), limit=MAX_COURTROOM_SESSIONS):
            if str(row.get("session_id") or "") == safe_session_id:
                return dict(row)
        raise HearingMediaWorkbenchError("courtroom_session_not_found", "The courtroom media session was not found in this matter.", status_code=404)

    @staticmethod
    def _public_courtroom_session(session: dict[str, Any]) -> dict[str, Any]:
        return {
            key: session.get(key)
            for key in (
                "session_id",
                "media_id",
                "media_hash",
                "media_kind",
                "clip_start_seconds",
                "clip_end_seconds",
                "transcript_id",
                "transcript_sha256",
                "created_at",
                "review_required",
                "private_notes_separate",
                "no_original_modified",
                "no_network",
            )
        }

    def _private_notes_path(self, session_id: str) -> Path:
        safe_session_id = _safe_work_id(session_id, field="session_id")
        path = self.courtroom_notes_dir / f"{safe_session_id}.json.enc"
        if path.exists() and path.is_symlink():
            raise HearingMediaWorkbenchError("private_notes_unavailable", "The separate private-note store is unavailable.", status_code=409)
        return path

    def _load_private_notes(self, session_id: str) -> dict[str, Any]:
        path = self._private_notes_path(session_id)
        if not path.exists():
            return {
                "schema_version": "courtroom_private_notes_v1",
                "matter_id": self.case_root.name,
                "session_id": _safe_work_id(session_id, field="session_id"),
                "notes": [],
            }
        try:
            value = self._encryptor.decrypt_json(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            raise HearingMediaWorkbenchError("private_notes_unavailable", "The separate private-note store is unavailable.", status_code=409) from exc
        if value.get("matter_id") != self.case_root.name or value.get("session_id") != _safe_work_id(session_id, field="session_id"):
            raise HearingMediaWorkbenchError("private_notes_scope_denied", "The separate private-note store is not available in this matter.", status_code=404)
        value["notes"] = _ensure_list(value.get("notes"), limit=MAX_PRIVATE_NOTES)
        return value

    def _save_private_notes(self, session_id: str, value: dict[str, Any]) -> None:
        path = self._private_notes_path(session_id)
        atomic_write_bytes(path, json.dumps(self._encryptor.encrypt_json(value), sort_keys=True).encode("utf-8"))

    def create_courtroom_session(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Prepare bounded, offline playback and transcript review without exposing private notes."""
        with self._lock:
            if payload.get("confirmed") is not True:
                raise HearingMediaWorkbenchError("courtroom_session_confirmation_required", "Confirm the local media review session before creating it.", status_code=400)
            state = self._load_state()
            media = self._find_media(state, media_id)
            source_hash = _safe_text(media.get("source_hash"), limit=64).casefold()
            if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
                raise HearingMediaWorkbenchError("courtroom_media_hash_required", "The imported media needs a SHA-256 source hash before courtroom review.", status_code=409)
            source_path = self._local_playback_source(media, payload.get("source_file"))
            if _sha256_file(source_path) != source_hash:
                raise HearingMediaWorkbenchError("courtroom_media_hash_mismatch", "The selected local media does not match the imported source hash.", status_code=409)
            transcript = self._transcript_for_media(state, media_id)
            session_id = _safe_work_id(payload.get("session_id"), field="session_id")
            sessions = [dict(row) for row in _ensure_list(state.get("courtroom_sessions"), limit=MAX_COURTROOM_SESSIONS)]
            if any(str(row.get("session_id") or "") == session_id for row in sessions):
                raise HearingMediaWorkbenchError("courtroom_session_id_conflict", "That courtroom session ID already exists in this matter.", status_code=409)
            duration = float(max(0, int(media.get("duration_seconds") or 0)))
            raw_start = payload.get("clip_start_seconds", 0)
            raw_end = payload.get("clip_end_seconds", duration)
            if isinstance(raw_start, bool) or isinstance(raw_end, bool):
                raise HearingMediaWorkbenchError("courtroom_clip_invalid", "Clip times must be numbers of seconds.", status_code=400)
            try:
                start, end = round(float(raw_start), 3), round(float(raw_end), 3)
            except (TypeError, ValueError) as exc:
                raise HearingMediaWorkbenchError("courtroom_clip_invalid", "Clip times must be numbers of seconds.", status_code=400) from exc
            if start < 0 or end <= start or (duration and end > duration):
                raise HearingMediaWorkbenchError("courtroom_clip_invalid", "Choose an ordered clip within the imported media duration.", status_code=400)
            session = {
                "session_id": session_id,
                "media_id": media_id,
                "media_hash": source_hash,
                "media_kind": media.get("media_kind"),
                "source_file": str(Path(payload.get("source_file")).as_posix()),
                "clip_start_seconds": start,
                "clip_end_seconds": end,
                "transcript_id": transcript["transcript_id"],
                "transcript_sha256": transcript["transcript_sha256"],
                "created_at": _utc_now(),
                "review_required": True,
                "private_notes_separate": True,
                "no_original_modified": True,
                "no_network": True,
            }
            sessions.append(session)
            state["courtroom_sessions"] = sessions[:MAX_COURTROOM_SESSIONS]
            self._record_history(
                state,
                _append_history(
                    "courtroom_session_created",
                    "courtroom_session",
                    session_id,
                    None,
                    self._public_courtroom_session(session),
                    f"Created a local courtroom playback review session for media {media_id}.",
                ),
            )
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "session": self._public_courtroom_session(session),
                "source": {"media_id": media_id, "media_hash": source_hash, "transcript_id": transcript["transcript_id"]},
                "private_notes_separate": True,
                "no_network": True,
            }

    def courtroom_session_source(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._courtroom_session(self._load_state(), session_id)
            return {
                "status": "pass",
                "review_required": True,
                "session": self._public_courtroom_session(session),
                "source": {
                    "media_id": session["media_id"],
                    "media_hash": session["media_hash"],
                    "transcript_id": session["transcript_id"],
                    "transcript_sha256": session["transcript_sha256"],
                },
                "notice": "This source binding does not establish authenticity, identity, completeness, admissibility, or legal effect.",
            }

    def courtroom_playback(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            session = self._courtroom_session(state, session_id)
            media = self._find_media(state, str(session["media_id"]))
            path = self._local_playback_source(media, session.get("source_file"))
            if _sha256_file(path) != session["media_hash"]:
                raise HearingMediaWorkbenchError("courtroom_media_hash_mismatch", "The local media no longer matches this review session's source hash.", status_code=409)
            size = path.stat().st_size
            if size > MAX_PLAYBACK_PREVIEW_BYTES:
                raise HearingMediaWorkbenchError("courtroom_playback_size_blocked", "This local media file is too large for the bounded embedded player preview.", status_code=413)
            data = path.read_bytes()
            media_type = self._playback_media_type(path, str(media.get("media_kind") or ""))
            return {
                "status": "pass",
                "review_required": True,
                "session": self._public_courtroom_session(session),
                "source": {"media_id": session["media_id"], "media_hash": session["media_hash"]},
                "data_url": f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}",
                "media_type": media_type,
                "keyboard_controls": {"space": "play_pause", "arrow_left": "seek_back_5_seconds", "arrow_right": "seek_forward_5_seconds"},
                "no_network": True,
            }

    def courtroom_sync(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            session = self._courtroom_session(state, session_id)
            raw_position = payload.get("position_seconds")
            if isinstance(raw_position, bool):
                raise HearingMediaWorkbenchError("courtroom_position_invalid", "Playback position must be a number of seconds.", status_code=400)
            try:
                position = round(float(raw_position), 3)
            except (TypeError, ValueError) as exc:
                raise HearingMediaWorkbenchError("courtroom_position_invalid", "Playback position must be a number of seconds.", status_code=400) from exc
            if position < session["clip_start_seconds"] or position > session["clip_end_seconds"]:
                raise HearingMediaWorkbenchError("courtroom_position_outside_clip", "Choose a playback position inside this review clip.", status_code=400)
            transcript = self._find_transcript(state, str(session["transcript_id"]))
            matching = [
                {
                    key: segment.get(key)
                    for key in ("segment_id", "start_seconds", "end_seconds", "text", "text_sha256", "speaker_label", "review_status")
                }
                for segment in _ensure_list(transcript.get("segments"), limit=MAX_SEGMENTS)
                if float(segment.get("start_seconds") or 0) <= position <= float(segment.get("end_seconds") or 0)
            ]
            return {
                "status": "pass",
                "review_required": True,
                "session_id": session["session_id"],
                "position_seconds": position,
                "segments": matching,
                "source": {"media_hash": session["media_hash"], "transcript_id": session["transcript_id"], "transcript_sha256": session["transcript_sha256"]},
                "notice": "Transcript synchronization presents review-required transcript segments and does not authenticate media, transcript accuracy, speaker identity, or legal effect.",
            }

    def add_courtroom_private_note(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            session = self._courtroom_session(state, session_id)
            if payload.get("confirmed") is not True:
                raise HearingMediaWorkbenchError("private_note_confirmation_required", "Confirm the private review note before saving it.", status_code=400)
            note_text = _safe_text(payload.get("note_text"), limit=8_000)
            reviewer_safe_id = _safe_work_id(payload.get("reviewer_safe_id"), field="reviewer_safe_id")
            if not note_text:
                raise HearingMediaWorkbenchError("private_note_required", "Enter a private review note.", status_code=400)
            notes = self._load_private_notes(session["session_id"])
            note = {
                "note_id": _safe_work_id(payload.get("note_id") or _safe_id("note", session["session_id"], note_text, _utc_now()), field="note_id"),
                "session_id": session["session_id"],
                "reviewer_safe_id": reviewer_safe_id,
                "note_text": note_text,
                "created_at": _utc_now(),
                "review_required": True,
                "not_in_session_or_export": True,
            }
            if any(str(row.get("note_id") or "") == note["note_id"] for row in notes["notes"]):
                raise HearingMediaWorkbenchError("private_note_id_conflict", "That private-note ID already exists for this session.", status_code=409)
            notes["notes"].append(note)
            self._save_private_notes(session["session_id"], notes)
            self._record_history(
                state,
                _append_history(
                    "courtroom_private_note_recorded",
                    "courtroom_private_note",
                    note["note_id"],
                    None,
                    {"note_id": note["note_id"], "note_sha256": _sha(note_text), "session_id": session["session_id"]},
                    "Recorded a separate encrypted private courtroom-review note.",
                ),
            )
            self._save_state(state)
            return {
                "status": "pass",
                "review_required": True,
                "note": note,
                "private_notes_separate": True,
                "not_in_session_or_export": True,
            }

    def courtroom_private_notes(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._courtroom_session(self._load_state(), session_id)
            notes = self._load_private_notes(session_id)
            return {
                "status": "pass",
                "review_required": True,
                "session_id": _safe_work_id(session_id, field="session_id"),
                "notes": [dict(row) for row in notes["notes"]],
                "private_notes_separate": True,
                "not_in_session_or_export": True,
            }

    def correct_transcript_segment(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an immutable human-review correction without changing transcript text."""
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            segment_id = _safe_text(payload.get("segment_id"), limit=120)
            corrected_text = _safe_text(payload.get("corrected_text"), limit=5_000)
            reviewer_notes = _safe_text(payload.get("reviewer_notes"), limit=2_000)
            if not segment_id:
                raise HearingMediaWorkbenchError("transcript_segment_required", "Choose a timestamped transcript segment.", status_code=400)
            if not corrected_text:
                raise HearingMediaWorkbenchError("corrected_text_required", "Enter the review correction text.", status_code=400)
            segment = next((dict(row) for row in transcript.get("segments") or [] if str(row.get("segment_id") or "") == segment_id), None)
            if segment is None:
                raise HearingMediaWorkbenchError("transcript_segment_not_found", "The selected transcript segment was not found.", status_code=404)
            correction = {
                "correction_id": _safe_id("transcript-correction", transcript["transcript_id"], segment_id, corrected_text, _utc_now()),
                "transcript_id": transcript["transcript_id"],
                "media_id": media_id,
                "media_hash": transcript.get("media_hash", ""),
                "segment_id": segment_id,
                "start_seconds": segment.get("start_seconds"),
                "end_seconds": segment.get("end_seconds"),
                "original_text_sha256": _sha(segment.get("text") or ""),
                "corrected_text": corrected_text,
                "corrected_text_sha256": _sha(corrected_text),
                "reviewer_notes": reviewer_notes,
                "created_at": _utc_now(),
                "review_status": "review_required",
                "notice": "This is a human correction proposal. The original transcript and its timestamped segment remain unchanged.",
                "review_required": True,
            }
            transcript["corrections"] = list(_ensure_list(transcript.get("corrections"), limit=MAX_SEGMENTS)) + [correction]
            transcript["correction_status"] = "review_required"
            transcript["updated_at"] = _utc_now()
            state["transcripts"] = [transcript if str(row.get("transcript_id") or "") == transcript["transcript_id"] else dict(row) for row in _ensure_list(state.get("transcripts"), limit=MAX_TRANSCRIPTS)]
            history = _append_history("transcript_correction_proposed", "transcript_segment", segment_id, {"transcript_sha256": transcript.get("transcript_sha256"), "segment_text_sha256": correction["original_text_sha256"]}, {"correction_id": correction["correction_id"], "corrected_text_sha256": correction["corrected_text_sha256"]}, "Recorded a timestamped transcript correction proposal; original transcript preserved.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "correction": correction, "source": {"media_id": media_id, "media_hash": transcript.get("media_hash", ""), "transcript_id": transcript["transcript_id"], "segment_id": segment_id, "start_seconds": segment.get("start_seconds"), "end_seconds": segment.get("end_seconds")}, "no_original_modified": True}

    def speaker_review(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            transcript = self._transcript_for_media(state, media_id)
            updates = _ensure_list(payload.get("labels") or payload.get("segment_updates"), limit=MAX_SEGMENTS)
            if not updates:
                raise HearingMediaWorkbenchError("speaker_labels_required", "Speaker labels are required.", status_code=400)
            if payload.get("confirmed") is not True:
                raise HearingMediaWorkbenchError("speaker_review_confirmation_required", "Confirm the human-reviewed speaker labels before recording them.", status_code=400)
            segments = [dict(segment) for segment in transcript.get("segments") or []]
            by_id = {str(segment.get("segment_id") or ""): segment for segment in segments}
            validated: list[tuple[dict[str, Any], str, str]] = []
            for raw in updates:
                if not isinstance(raw, dict):
                    raise HearingMediaWorkbenchError("speaker_label_invalid", "Each speaker-label review item must be an object.", status_code=400)
                segment_id = _safe_text(raw.get("segment_id"), limit=120)
                if not segment_id:
                    raise HearingMediaWorkbenchError("speaker_segment_required", "Each speaker label must identify a transcript segment.", status_code=400)
                if segment_id not in by_id:
                    raise HearingMediaWorkbenchError("speaker_segment_not_found", "A selected transcript segment was not found.", status_code=404)
                before = str(by_id[segment_id].get("speaker_label") or "unknown")
                after = _safe_text(raw.get("speaker_label") or raw.get("label"), limit=120)
                if not after:
                    raise HearingMediaWorkbenchError("speaker_label_required", "Each selected segment needs a reviewer-supplied speaker label.", status_code=400)
                validated.append((by_id[segment_id], before, after))
            changes: list[dict[str, Any]] = []
            for segment, before, after in validated:
                segment_id = str(segment.get("segment_id") or "")
                segment["speaker_label"] = after
                segment["speaker_label_source"] = "user_review"
                segment["speaker_reviewed_at"] = _utc_now()
                segment["speaker_label_confirmed"] = True
                changes.append({
                    "segment_id": segment_id,
                    "before": before,
                    "after": after,
                    "start_seconds": segment.get("start_seconds"),
                    "end_seconds": segment.get("end_seconds"),
                    "text_sha256": segment.get("text_sha256") or _sha(segment.get("text") or ""),
                    "speaker_label_source": "user_review",
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
                "source": {
                    "media_id": media_id,
                    "media_hash": transcript.get("media_hash", ""),
                    "transcript_id": transcript["transcript_id"],
                    "segments": [{key: row.get(key) for key in ("segment_id", "start_seconds", "end_seconds", "text_sha256")} for row in changes],
                },
                "speaker_identity_inference_blocked": True,
                "no_biometric_identity_inference": True,
            }

    def generate_keyframes(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate encrypted local keyframes from a source-hash-bound video in the active matter."""
        with self._lock:
            state = self._load_state()
            media = self._find_media(state, media_id)
            if str(media.get("media_kind") or "") != "video":
                raise HearingMediaWorkbenchError("video_media_required", "Keyframes can only be generated from an imported video record.", status_code=400)
            expected_hash = _safe_text(media.get("source_hash"), limit=64).casefold()
            if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
                raise HearingMediaWorkbenchError("video_source_hash_required", "The imported video needs a SHA-256 source hash before keyframe review.", status_code=409)
            source_path = self._local_video_source(payload.get("source_file"))
            actual_hash = _sha256_file(source_path)
            if actual_hash != expected_hash:
                raise HearingMediaWorkbenchError("video_source_hash_mismatch", "The selected local video no longer matches the imported source hash.", status_code=409)
            raw_timestamps = payload.get("timestamps_seconds")
            duration = max(0, int(media.get("duration_seconds") or 0))
            if raw_timestamps is None:
                timestamps = [0.0] if duration < 2 else [0.0, round(duration / 2, 3), float(duration - 1)]
            elif isinstance(raw_timestamps, list):
                timestamps = []
                for raw in raw_timestamps[:MAX_KEYFRAMES_PER_REVIEW]:
                    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                        raise HearingMediaWorkbenchError("keyframe_timestamp_invalid", "Each keyframe timestamp must be a non-negative number of seconds.", status_code=400)
                    value = round(float(raw), 3)
                    if value < 0 or (duration and value > duration):
                        raise HearingMediaWorkbenchError("keyframe_timestamp_invalid", "A keyframe timestamp is outside the imported video duration.", status_code=400)
                    timestamps.append(value)
            else:
                raise HearingMediaWorkbenchError("keyframe_timestamps_invalid", "Keyframe timestamps must be a list of seconds.", status_code=400)
            timestamps = sorted(set(timestamps))[:MAX_KEYFRAMES_PER_REVIEW]
            if not timestamps:
                raise HearingMediaWorkbenchError("keyframe_timestamp_required", "Choose at least one local video timestamp.", status_code=400)
            try:
                import cv2  # type: ignore[import-not-found]
            except Exception as exc:
                raise HearingMediaWorkbenchError("local_video_decoder_unavailable", "No admitted local video decoder is available for keyframe review.", status_code=409) from exc
            capture = cv2.VideoCapture(str(source_path))
            if not capture.isOpened():
                capture.release()
                raise HearingMediaWorkbenchError("video_decode_unavailable", "The selected local video could not be opened for keyframe review.", status_code=422)
            review_id = _safe_id("keyframe-review", media_id, expected_hash, timestamps, _utc_now())
            review_dir = self.keyframes_dir / media_id / review_id
            review_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            frames: list[dict[str, Any]] = []
            unavailable_timestamps: list[float] = []
            try:
                for index, timestamp in enumerate(timestamps, start=1):
                    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                    ok, image = capture.read()
                    if not ok or image is None:
                        unavailable_timestamps.append(timestamp)
                        continue
                    encoded_ok, encoded = cv2.imencode(".png", image)
                    if not encoded_ok:
                        unavailable_timestamps.append(timestamp)
                        continue
                    image_bytes = bytes(encoded.tobytes())
                    if not image_bytes or len(image_bytes) > MAX_KEYFRAME_BYTES:
                        unavailable_timestamps.append(timestamp)
                        continue
                    frame_id = f"frame-{index:04d}"
                    artifact_path = review_dir / f"{frame_id}.png.enc"
                    envelope = self._encryptor.encrypt_json({"schema_version": "hearing_media_keyframe_v1", "content_b64": base64.b64encode(image_bytes).decode("ascii")})
                    atomic_write_bytes(artifact_path, json.dumps(envelope, sort_keys=True).encode("utf-8"))
                    frames.append({
                        "frame_id": frame_id,
                        "timestamp_seconds": timestamp,
                        "visual_sha256": hashlib.sha256(image_bytes).hexdigest(),
                        "byte_size": len(image_bytes),
                        "artifact_id": f"{review_id}:{frame_id}",
                        "review_required": True,
                    })
            finally:
                capture.release()
            if not frames:
                raise HearingMediaWorkbenchError("keyframe_generation_unavailable", "No requested local video keyframe could be generated.", status_code=422)
            review = {
                "review_id": review_id,
                "media_id": media_id,
                "media_hash": expected_hash,
                "source_file_hash": actual_hash,
                "frame_count": len(frames),
                "frames": frames,
                "unavailable_timestamps": unavailable_timestamps,
                "annotations": [],
                "review_required": True,
                "status": "review_required" if unavailable_timestamps else "generated_review_required",
                "local_only": True,
                "no_original_modified": True,
                "no_authenticity_determination": True,
                "generated_at": _utc_now(),
            }
            reviews = [dict(row) for row in _ensure_list(state.get("keyframe_reviews"), limit=MAX_KEYFRAME_REVIEWS)]
            reviews.append(review)
            state["keyframe_reviews"] = reviews[:MAX_KEYFRAME_REVIEWS]
            history = _append_history("generate_keyframes", "keyframe_review", review_id, {"media_hash": expected_hash}, {"frame_visual_hashes": [frame["visual_sha256"] for frame in frames], "unavailable_timestamps": unavailable_timestamps}, "Generated encrypted local video keyframe derivatives for human review.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "keyframe_review": review, "source": {"media_id": media_id, "media_hash": expected_hash}, "no_original_modified": True}

    def annotate_keyframe(self, media_id: str, review_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            review = self._keyframe_review(state, media_id, review_id)
            if payload.get("confirmed") is not True:
                raise HearingMediaWorkbenchError("keyframe_annotation_confirmation_required", "Confirm the human-reviewed keyframe annotation before recording it.", status_code=400)
            frame_id = _safe_text(payload.get("frame_id"), limit=120)
            annotation_text = _safe_text(payload.get("annotation_text"), limit=2_000)
            if not frame_id or not annotation_text:
                raise HearingMediaWorkbenchError("keyframe_annotation_required", "Choose a generated keyframe and enter a review annotation.", status_code=400)
            frame = next((dict(row) for row in review.get("frames") or [] if str(row.get("frame_id") or "") == frame_id), None)
            if frame is None:
                raise HearingMediaWorkbenchError("keyframe_not_found", "The selected generated keyframe was not found.", status_code=404)
            annotation = {
                "annotation_id": _safe_id("keyframe-annotation", review_id, frame_id, annotation_text, _utc_now()),
                "frame_id": frame_id,
                "timestamp_seconds": frame.get("timestamp_seconds"),
                "visual_sha256": frame.get("visual_sha256"),
                "annotation_text": annotation_text,
                "review_required": True,
                "no_authenticity_determination": True,
                "created_at": _utc_now(),
            }
            review["annotations"] = list(_ensure_list(review.get("annotations"), limit=MAX_HISTORY)) + [annotation]
            review["status"] = "review_required"
            reviews = [review if str(row.get("review_id") or "") == review_id and str(row.get("media_id") or "") == media_id else dict(row) for row in _ensure_list(state.get("keyframe_reviews"), limit=MAX_KEYFRAME_REVIEWS)]
            state["keyframe_reviews"] = reviews
            history = _append_history("annotate_keyframe", "keyframe", frame_id, {"visual_sha256": frame.get("visual_sha256")}, {"annotation_id": annotation["annotation_id"], "annotation_sha256": _sha(annotation_text)}, "Recorded a human keyframe annotation; no authenticity determination was made.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "annotation": annotation, "source": {"media_id": media_id, "media_hash": review.get("media_hash"), "review_id": review_id, "frame_id": frame_id, "timestamp_seconds": frame.get("timestamp_seconds"), "visual_sha256": frame.get("visual_sha256")}}

    def keyframe_preview(self, media_id: str, review_id: str, frame_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            review = self._keyframe_review(state, media_id, review_id)
            frame = next((dict(row) for row in review.get("frames") or [] if str(row.get("frame_id") or "") == frame_id), None)
            if frame is None:
                raise HearingMediaWorkbenchError("keyframe_not_found", "The selected generated keyframe was not found.", status_code=404)
            artifact_path = self.keyframes_dir / media_id / review_id / f"{frame_id}.png.enc"
            try:
                envelope = json.loads(artifact_path.read_text(encoding="utf-8"))
                decrypted = self._encryptor.decrypt_json(envelope)
                image_bytes = base64.b64decode(str(decrypted.get("content_b64") or ""), validate=True)
            except Exception as exc:
                raise HearingMediaWorkbenchError("keyframe_artifact_unavailable", "The encrypted keyframe artifact is unavailable.", status_code=409) from exc
            if hashlib.sha256(image_bytes).hexdigest() != frame.get("visual_sha256"):
                raise HearingMediaWorkbenchError("keyframe_artifact_hash_mismatch", "The encrypted keyframe artifact no longer matches its receipt.", status_code=409)
            return {"status": "pass", "review_required": True, "frame": frame, "source": {"media_id": media_id, "media_hash": review.get("media_hash"), "review_id": review_id}, "data_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")}

    def _validated_redaction_intervals(self, payload: dict[str, Any], *, field: str) -> list[dict[str, float]]:
        raw_intervals = _ensure_list(payload.get(field), limit=MAX_REDACTION_INTERVALS)
        if not raw_intervals:
            raise HearingMediaWorkbenchError("redaction_interval_required", "Choose at least one exact local-media redaction interval.", status_code=400)
        intervals: list[dict[str, float]] = []
        for raw in raw_intervals:
            if not isinstance(raw, dict):
                raise HearingMediaWorkbenchError("redaction_interval_invalid", "Each redaction interval must be an object.", status_code=400)
            start = raw.get("start_seconds")
            end = raw.get("end_seconds")
            if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise HearingMediaWorkbenchError("redaction_interval_invalid", "Redaction intervals require numeric start and end seconds.", status_code=400)
            start_value, end_value = round(float(start), 3), round(float(end), 3)
            if start_value < 0 or end_value <= start_value:
                raise HearingMediaWorkbenchError("redaction_interval_invalid", "Each redaction interval needs a non-negative start before its end.", status_code=400)
            intervals.append({"start_seconds": start_value, "end_seconds": end_value})
        return intervals

    def _redaction_artifact_bytes(self, media_id: str, derivative_id: str, suffix: str) -> bytes:
        artifact_path = self.media_redactions_dir / media_id / f"{derivative_id}.{suffix}.enc"
        try:
            envelope = json.loads(artifact_path.read_text(encoding="utf-8"))
            decrypted = self._encryptor.decrypt_json(envelope)
            return base64.b64decode(str(decrypted.get("content_b64") or ""), validate=True)
        except Exception as exc:
            raise HearingMediaWorkbenchError("media_redaction_artifact_unavailable", "The encrypted media redaction derivative is unavailable.", status_code=409) from exc

    def _create_wav_mute_derivative(self, source_path: Path, intervals: list[dict[str, float]]) -> bytes:
        try:
            with wave.open(str(source_path), "rb") as reader:
                if reader.getcomptype() != "NONE":
                    raise HearingMediaWorkbenchError("audio_redaction_format_blocked", "Only uncompressed local WAV audio is available for muting review.", status_code=415)
                params = reader.getparams()
                frames = bytearray(reader.readframes(reader.getnframes()))
        except HearingMediaWorkbenchError:
            raise
        except Exception as exc:
            raise HearingMediaWorkbenchError("audio_decode_unavailable", "The selected local WAV audio could not be opened for muting review.", status_code=422) from exc
        frame_width = int(params.nchannels) * int(params.sampwidth)
        if frame_width < 1 or int(params.framerate) < 1:
            raise HearingMediaWorkbenchError("audio_decode_unavailable", "The selected local WAV audio has unsupported audio parameters.", status_code=422)
        frame_count = len(frames) // frame_width
        for interval in intervals:
            start_frame = max(0, min(frame_count, int(interval["start_seconds"] * params.framerate)))
            end_frame = max(start_frame, min(frame_count, int(interval["end_seconds"] * params.framerate)))
            frames[start_frame * frame_width : end_frame * frame_width] = b"\x00" * ((end_frame - start_frame) * frame_width)
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setparams(params)
            writer.writeframes(bytes(frames))
        derivative = output.getvalue()
        if not derivative or len(derivative) > MAX_REDACTION_DERIVATIVE_BYTES:
            raise HearingMediaWorkbenchError("media_redaction_derivative_size_blocked", "The local audio redaction derivative exceeds the protected preview limit.", status_code=413)
        return derivative

    def _create_video_blur_derivative(self, source_path: Path, intervals: list[dict[str, float]], regions: list[dict[str, float]], target_path: Path) -> bytes:
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception as exc:
            raise HearingMediaWorkbenchError("local_video_decoder_unavailable", "No admitted local video decoder is available for blur review.", status_code=409) from exc
        capture = cv2.VideoCapture(str(source_path))
        if not capture.isOpened():
            capture.release()
            raise HearingMediaWorkbenchError("video_decode_unavailable", "The selected local video could not be opened for blur review.", status_code=422)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 24.0
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width < 2 or height < 2:
            capture.release()
            raise HearingMediaWorkbenchError("video_decode_unavailable", "The selected local video has unsupported dimensions.", status_code=422)
        writer = cv2.VideoWriter(str(target_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
        if not writer.isOpened():
            capture.release(); writer.release()
            raise HearingMediaWorkbenchError("local_video_encoder_unavailable", "No admitted local video encoder is available for blur review.", status_code=409)
        frame_index = 0
        try:
            while True:
                ok, image = capture.read()
                if not ok or image is None:
                    break
                timestamp = frame_index / fps
                if any(interval["start_seconds"] <= timestamp < interval["end_seconds"] for interval in intervals):
                    for region in regions:
                        left = max(0, min(width - 1, int(region["x"] * width)))
                        top = max(0, min(height - 1, int(region["y"] * height)))
                        right = max(left + 1, min(width, int((region["x"] + region["width"]) * width)))
                        bottom = max(top + 1, min(height, int((region["y"] + region["height"]) * height)))
                        roi = image[top:bottom, left:right]
                        if roi.size:
                            image[top:bottom, left:right] = cv2.GaussianBlur(roi, (0, 0), 7)
                writer.write(image)
                frame_index += 1
        finally:
            capture.release(); writer.release()
        try:
            derivative = target_path.read_bytes()
        except OSError as exc:
            raise HearingMediaWorkbenchError("media_redaction_artifact_unavailable", "The local video blur derivative could not be read.", status_code=409) from exc
        if not derivative or len(derivative) > MAX_REDACTION_DERIVATIVE_BYTES:
            raise HearingMediaWorkbenchError("media_redaction_derivative_size_blocked", "The local video redaction derivative exceeds the protected preview limit.", status_code=413)
        return derivative

    def create_media_redaction_derivative(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a protected local WAV-mute or AVI-blur derivative after explicit human confirmation."""
        with self._lock:
            if payload.get("confirmed") is not True:
                raise HearingMediaWorkbenchError("media_redaction_confirmation_required", "Confirm the human-reviewed media redaction before creating a derivative.", status_code=400)
            state = self._load_state()
            media = self._find_media(state, media_id)
            expected_hash = _safe_text(media.get("source_hash"), limit=64).casefold()
            if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
                raise HearingMediaWorkbenchError("media_redaction_source_hash_required", "The imported media needs a SHA-256 source hash before redaction.", status_code=409)
            kind = str(media.get("media_kind") or "")
            derivative_id = _safe_id("media-redaction", media_id, expected_hash, payload.get("mute_intervals"), payload.get("blur_regions"), _utc_now())
            derivative_dir = self.media_redactions_dir / media_id
            derivative_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary_path: Path | None = None
            if kind == "audio":
                source_path = self._local_audio_source(payload.get("source_file"))
                intervals = self._validated_redaction_intervals(payload, field="mute_intervals")
                actual_hash = _sha256_file(source_path)
                if actual_hash != expected_hash:
                    raise HearingMediaWorkbenchError("media_redaction_source_hash_mismatch", "The selected local audio no longer matches the imported source hash.", status_code=409)
                derivative_bytes = self._create_wav_mute_derivative(source_path, intervals)
                suffix, media_type, redaction_kind = "wav", "audio/wav", "audio_mute"
                operation = {"mute_intervals": intervals}
            elif kind == "video":
                source_path = self._local_video_source(payload.get("source_file"))
                intervals = self._validated_redaction_intervals(payload, field="blur_intervals")
                raw_regions = _ensure_list(payload.get("blur_regions"), limit=MAX_REDACTION_INTERVALS)
                if not raw_regions:
                    raise HearingMediaWorkbenchError("blur_region_required", "Choose at least one normalized blur region for the local video review.", status_code=400)
                regions: list[dict[str, float]] = []
                for raw in raw_regions:
                    if not isinstance(raw, dict) or any(isinstance(raw.get(key), bool) or not isinstance(raw.get(key), (int, float)) for key in ("x", "y", "width", "height")):
                        raise HearingMediaWorkbenchError("blur_region_invalid", "Each blur region requires numeric x, y, width, and height values.", status_code=400)
                    region = {key: round(float(raw[key]), 4) for key in ("x", "y", "width", "height")}
                    if region["x"] < 0 or region["y"] < 0 or region["width"] <= 0 or region["height"] <= 0 or region["x"] + region["width"] > 1 or region["y"] + region["height"] > 1:
                        raise HearingMediaWorkbenchError("blur_region_invalid", "Blur regions must stay within the normalized local video frame.", status_code=400)
                    regions.append(region)
                actual_hash = _sha256_file(source_path)
                if actual_hash != expected_hash:
                    raise HearingMediaWorkbenchError("media_redaction_source_hash_mismatch", "The selected local video no longer matches the imported source hash.", status_code=409)
                temporary_path = derivative_dir / f"{derivative_id}.partial.avi"
                try:
                    derivative_bytes = self._create_video_blur_derivative(source_path, intervals, regions, temporary_path)
                finally:
                    if temporary_path.exists():
                        temporary_path.unlink(missing_ok=True)
                suffix, media_type, redaction_kind = "avi", "video/x-msvideo", "video_blur"
                operation = {"blur_intervals": intervals, "blur_regions": regions}
            else:
                raise HearingMediaWorkbenchError("media_redaction_kind_unsupported", "Only imported audio or video media can receive a local redaction derivative.", status_code=400)
            derivative_hash = hashlib.sha256(derivative_bytes).hexdigest()
            artifact_path = derivative_dir / f"{derivative_id}.{suffix}.enc"
            envelope = self._encryptor.encrypt_json({"schema_version": "hearing_media_redaction_derivative_v1", "content_b64": base64.b64encode(derivative_bytes).decode("ascii"), "media_type": media_type})
            atomic_write_bytes(artifact_path, json.dumps(envelope, sort_keys=True).encode("utf-8"))
            derivative = {
                "derivative_id": derivative_id,
                "media_id": media_id,
                "media_hash": expected_hash,
                "source_file_hash": actual_hash,
                "redaction_kind": redaction_kind,
                "operation": operation,
                "derivative_sha256": derivative_hash,
                "byte_size": len(derivative_bytes),
                "media_type": media_type,
                "review_required": True,
                "no_original_modified": True,
                "no_authenticity_determination": True,
                "created_at": _utc_now(),
            }
            derivatives = [dict(row) for row in _ensure_list(state.get("media_redaction_derivatives"), limit=MAX_EXPORTS)]
            derivatives.append(derivative)
            state["media_redaction_derivatives"] = derivatives[:MAX_EXPORTS]
            history = _append_history("create_media_redaction_derivative", "media_redaction", derivative_id, {"media_hash": expected_hash}, {"derivative_sha256": derivative_hash, "redaction_kind": redaction_kind}, "Created an encrypted local media redaction derivative for human review; original media preserved.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "derivative": derivative, "source": {"media_id": media_id, "media_hash": expected_hash}, "no_original_modified": True}

    def media_redaction_preview(self, media_id: str, derivative_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            derivative = next((dict(row) for row in _ensure_list(state.get("media_redaction_derivatives"), limit=MAX_EXPORTS) if str(row.get("media_id") or "") == media_id and str(row.get("derivative_id") or "") == derivative_id), None)
            if derivative is None:
                raise HearingMediaWorkbenchError("media_redaction_not_found", "The selected media redaction derivative was not found in this matter.", status_code=404)
            suffix = "wav" if derivative.get("redaction_kind") == "audio_mute" else "avi"
            content = self._redaction_artifact_bytes(media_id, derivative_id, suffix)
            if hashlib.sha256(content).hexdigest() != derivative.get("derivative_sha256"):
                raise HearingMediaWorkbenchError("media_redaction_artifact_hash_mismatch", "The encrypted media redaction derivative no longer matches its receipt.", status_code=409)
            return {"status": "pass", "review_required": True, "derivative": derivative, "source": {"media_id": media_id, "media_hash": derivative.get("media_hash")}, "data_url": f"data:{derivative.get('media_type')};base64," + base64.b64encode(content).decode("ascii")}

    def reconstruct_screenshot_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Order user-supplied screenshot observations without inferring omitted messages or authenticity."""
        with self._lock:
            state = self._load_state()
            conversation_id = _safe_work_id(payload.get("conversation_id"), field="conversation_id")
            raw_rows = _ensure_list(payload.get("screenshots"), limit=500)
            if not raw_rows:
                raise HearingMediaWorkbenchError("screenshot_required", "Add at least one source-bound screenshot observation.", status_code=400)
            existing_ids = {str(row.get("conversation_id") or "") for row in _ensure_list(state.get("screenshot_conversations"), limit=MAX_EXPORTS)}
            if conversation_id in existing_ids:
                raise HearingMediaWorkbenchError("screenshot_conversation_id_conflict", "That screenshot conversation ID already exists in this matter.", status_code=409)
            observations: list[dict[str, Any]] = []
            seen_screenshots: set[str] = set()
            uncertainties: list[dict[str, Any]] = []
            for index, raw in enumerate(raw_rows, start=1):
                if not isinstance(raw, dict):
                    raise HearingMediaWorkbenchError("screenshot_invalid", "Each screenshot observation must be an object.", status_code=400)
                screenshot_id = _safe_work_id(raw.get("screenshot_id"), field="screenshot_id")
                if screenshot_id in seen_screenshots:
                    raise HearingMediaWorkbenchError("screenshot_id_conflict", "Each screenshot observation needs a different screenshot ID.", status_code=409)
                seen_screenshots.add(screenshot_id)
                source_hash = _safe_text(raw.get("source_hash"), limit=64).casefold()
                if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
                    raise HearingMediaWorkbenchError("screenshot_source_hash_invalid", "Each screenshot needs a SHA-256 source hash.", status_code=400)
                visible_timestamp = _safe_text(raw.get("visible_timestamp"), limit=80)
                timestamp_seconds: float | None = None
                timestamp_status = "not_visible"
                if visible_timestamp and visible_timestamp.casefold() not in {"unknown", "not_visible", "not shown"}:
                    try:
                        parsed = datetime.fromisoformat(visible_timestamp.replace("Z", "+00:00"))
                        timestamp_seconds = parsed.timestamp() if parsed.tzinfo else parsed.replace(tzinfo=UTC).timestamp()
                        timestamp_status = "visible_with_timezone" if parsed.tzinfo else "visible_timezone_unknown"
                    except ValueError:
                        timestamp_status = "unparseable_visible_timestamp"
                timezone_label = _safe_text(raw.get("timezone") or "unknown", limit=80)
                order_hint = raw.get("order_hint")
                if order_hint is not None and (isinstance(order_hint, bool) or not isinstance(order_hint, int) or order_hint < 0 or order_hint > 100_000):
                    raise HearingMediaWorkbenchError("screenshot_order_hint_invalid", "A screenshot order hint must be a bounded non-negative integer.", status_code=400)
                observation = {
                    "screenshot_id": screenshot_id,
                    "source_hash": source_hash,
                    "visible_timestamp": visible_timestamp or "not_visible",
                    "timestamp_status": timestamp_status,
                    "timezone": timezone_label,
                    "order_hint": order_hint if isinstance(order_hint, int) else index,
                    "review_annotation": _safe_text(raw.get("review_annotation"), limit=2_000),
                    "review_required": True,
                    "no_sender_identity_inference": True,
                    "no_message_completeness_inference": True,
                }
                observations.append(observation)
                if timestamp_status != "visible_with_timezone":
                    uncertainties.append({"screenshot_id": screenshot_id, "kind": timestamp_status, "notice": "Ordering may be uncertain because the visible timestamp or timezone is incomplete."})
            ordered = sorted(observations, key=lambda row: (row["timestamp_status"] in {"not_visible", "unparseable_visible_timestamp"}, row["visible_timestamp"] if row["timestamp_status"] != "not_visible" else "9999-12-31", int(row["order_hint"]), str(row["screenshot_id"])))
            gaps: list[dict[str, Any]] = []
            previous: dict[str, Any] | None = None
            for row in ordered:
                if previous is not None:
                    previous_time, current_time = previous.get("visible_timestamp"), row.get("visible_timestamp")
                    try:
                        before = datetime.fromisoformat(str(previous_time).replace("Z", "+00:00"))
                        after = datetime.fromisoformat(str(current_time).replace("Z", "+00:00"))
                        seconds = abs((after.replace(tzinfo=UTC) if after.tzinfo is None else after).timestamp() - (before.replace(tzinfo=UTC) if before.tzinfo is None else before).timestamp())
                    except (TypeError, ValueError):
                        seconds = None
                    if seconds is None:
                        gaps.append({"before_screenshot_id": previous["screenshot_id"], "after_screenshot_id": row["screenshot_id"], "kind": "ordering_gap_unresolved", "notice": "No complete visible timestamp pair is available between these screenshots."})
                    elif seconds > 6 * 60 * 60:
                        gaps.append({"before_screenshot_id": previous["screenshot_id"], "after_screenshot_id": row["screenshot_id"], "kind": "large_visible_timestamp_gap", "seconds": round(seconds, 3), "notice": "The visible timestamps are separated by more than six hours; this does not prove omitted messages."})
                previous = row
            hash_counts: dict[str, int] = {}
            for row in observations:
                hash_counts[row["source_hash"]] = hash_counts.get(row["source_hash"], 0) + 1
            for source_hash, count in sorted(hash_counts.items()):
                if count > 1:
                    uncertainties.append({"kind": "duplicate_screenshot_hash", "source_hash": source_hash, "count": count, "notice": "More than one observation refers to the same screenshot hash."})
            reconstruction = {
                "conversation_id": conversation_id,
                "screenshot_count": len(ordered),
                "ordered_screenshots": ordered,
                "gaps": gaps,
                "uncertainties": uncertainties,
                "review_required": True,
                "status": "review_required" if gaps or uncertainties else "ordered_review_required",
                "no_authenticity_determination": True,
                "no_message_completeness_inference": True,
                "no_sender_identity_inference": True,
                "created_at": _utc_now(),
            }
            conversations = [dict(row) for row in _ensure_list(state.get("screenshot_conversations"), limit=MAX_EXPORTS)]
            conversations.append(reconstruction)
            state["screenshot_conversations"] = conversations[:MAX_EXPORTS]
            history = _append_history("reconstruct_screenshot_conversation", "screenshot_conversation", conversation_id, None, {"screenshot_source_hashes": [row["source_hash"] for row in ordered], "reconstruction_sha256": _sha(reconstruction)}, "Ordered source-bound screenshot observations with visible gaps and uncertainty retained for review.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "reconstruction": reconstruction}

    def screenshot_conversations(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            return {"status": "pass", "review_required": True, "conversations": _ensure_list(state.get("screenshot_conversations"), limit=MAX_EXPORTS), "no_authenticity_determination": True, "no_message_completeness_inference": True}

    def screenshot_observation(self, conversation_id: str, screenshot_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            conversation = next((dict(row) for row in _ensure_list(state.get("screenshot_conversations"), limit=MAX_EXPORTS) if str(row.get("conversation_id") or "") == conversation_id), None)
            if conversation is None:
                raise HearingMediaWorkbenchError("screenshot_conversation_not_found", "The selected screenshot conversation was not found in this matter.", status_code=404)
            observation = next((dict(row) for row in conversation.get("ordered_screenshots") or [] if str(row.get("screenshot_id") or "") == screenshot_id), None)
            if observation is None:
                raise HearingMediaWorkbenchError("screenshot_observation_not_found", "The selected screenshot observation was not found in this conversation.", status_code=404)
            return {"status": "pass", "review_required": True, "observation": observation, "source": {"conversation_id": conversation_id, "screenshot_id": screenshot_id, "source_hash": observation.get("source_hash")}, "no_authenticity_determination": True}

    def inspect_media_metadata(self, media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Record a bounded local metadata inspection without treating metadata as authentication."""
        with self._lock:
            state = self._load_state()
            media = self._find_media(state, media_id)
            expected_hash = _safe_text(media.get("source_hash"), limit=64).casefold()
            if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
                raise HearingMediaWorkbenchError("metadata_source_hash_required", "The imported media needs a SHA-256 source hash before metadata inspection.", status_code=409)
            kind = str(media.get("media_kind") or "")
            if kind == "image":
                source_path = self._local_image_source(payload.get("source_file"))
            elif kind == "audio":
                source_path = self._local_audio_source(payload.get("source_file"))
            elif kind == "video":
                source_path = self._local_video_source(payload.get("source_file"))
            else:
                raise HearingMediaWorkbenchError("metadata_kind_unsupported", "The imported media type is unavailable for local metadata inspection.", status_code=400)
            actual_hash = _sha256_file(source_path)
            if actual_hash != expected_hash:
                raise HearingMediaWorkbenchError("metadata_source_hash_mismatch", "The selected local media no longer matches the imported source hash.", status_code=409)
            technical: dict[str, Any] = {"media_kind": kind, "file_size_bytes": source_path.stat().st_size}
            exif: dict[str, Any] = {"status": "not_applicable"}
            if kind == "image":
                try:
                    from PIL import Image

                    with Image.open(source_path) as image:
                        raw_exif = image.getexif()
                        capture_time = _safe_text(raw_exif.get(36867) or raw_exif.get(306), limit=120)
                        device_make = _safe_text(raw_exif.get(271), limit=120)
                        device_model = _safe_text(raw_exif.get(272), limit=120)
                        technical.update({"format": _safe_text(image.format or "unknown", limit=32), "width": int(image.width), "height": int(image.height), "color_mode": _safe_text(image.mode or "unknown", limit=32)})
                        exif = {"status": "available" if raw_exif else "not_present", "capture_time": capture_time or "not_present", "device_make": device_make or "not_present", "device_model": device_model or "not_present", "gps_metadata": "present_value_withheld" if 34853 in raw_exif else "not_present"}
                except HearingMediaWorkbenchError:
                    raise
                except Exception as exc:
                    raise HearingMediaWorkbenchError("image_metadata_unavailable", "The selected local image could not be inspected.", status_code=422) from exc
            elif kind == "audio":
                try:
                    with wave.open(str(source_path), "rb") as reader:
                        frames, rate = int(reader.getnframes()), int(reader.getframerate())
                        technical.update({"format": "wav", "channels": int(reader.getnchannels()), "sample_width_bytes": int(reader.getsampwidth()), "sample_rate_hz": rate, "frame_count": frames, "duration_seconds": round(frames / rate, 3) if rate else None, "compression": _safe_text(reader.getcomptype(), limit=32)})
                except Exception as exc:
                    raise HearingMediaWorkbenchError("audio_metadata_unavailable", "The selected local WAV audio could not be inspected.", status_code=422) from exc
                exif = {"status": "not_applicable_for_wav"}
            else:
                try:
                    import cv2  # type: ignore[import-not-found]
                except Exception as exc:
                    raise HearingMediaWorkbenchError("local_video_decoder_unavailable", "No admitted local video decoder is available for metadata inspection.", status_code=409) from exc
                capture = cv2.VideoCapture(str(source_path))
                if not capture.isOpened():
                    capture.release()
                    raise HearingMediaWorkbenchError("video_metadata_unavailable", "The selected local video could not be inspected.", status_code=422)
                try:
                    frames, fps = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0), float(capture.get(cv2.CAP_PROP_FPS) or 0)
                    technical.update({"container": source_path.suffix.casefold().lstrip("."), "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0), "frame_count": frames, "fps": round(fps, 3) if fps else None, "duration_seconds": round(frames / fps, 3) if fps else None})
                finally:
                    capture.release()
                exif = {"status": "not_available_from_local_video_decoder"}
            raw_claims = payload.get("claimed_metadata") or {}
            if not isinstance(raw_claims, dict):
                raise HearingMediaWorkbenchError("metadata_claims_invalid", "Claimed metadata must be an object when supplied.", status_code=400)
            claims = {key: _safe_text(raw_claims.get(key), limit=240) for key in ("captured_at", "device_label", "source_hash") if _safe_text(raw_claims.get(key), limit=240)}
            conflicts: list[dict[str, Any]] = []
            if claims.get("source_hash") and claims["source_hash"].casefold() != actual_hash:
                conflicts.append({"field": "source_hash", "status": "claimed_hash_differs_from_selected_local_source"})
            capture_time = str(exif.get("capture_time") or "")
            if claims.get("captured_at") and capture_time not in {"", "not_present"} and claims["captured_at"] != capture_time:
                conflicts.append({"field": "captured_at", "status": "claimed_time_differs_from_available_image_metadata"})
            elif claims.get("captured_at") and capture_time in {"", "not_present"}:
                conflicts.append({"field": "captured_at", "status": "claimed_time_unverified_metadata_absent"})
            derivative_effects = {
                "keyframe_reviews": [{"review_id": row.get("review_id"), "frame_count": row.get("frame_count")} for row in _ensure_list(state.get("keyframe_reviews"), limit=MAX_KEYFRAME_REVIEWS) if str(row.get("media_id") or "") == media_id],
                "media_redaction_derivatives": [{"derivative_id": row.get("derivative_id"), "redaction_kind": row.get("redaction_kind"), "derivative_sha256": row.get("derivative_sha256")} for row in _ensure_list(state.get("media_redaction_derivatives"), limit=MAX_EXPORTS) if str(row.get("media_id") or "") == media_id],
            }
            inspection_id = _safe_id("media-metadata", media_id, actual_hash, technical, claims, _utc_now())
            inspection = {"inspection_id": inspection_id, "media_id": media_id, "media_hash": expected_hash, "source_file_hash": actual_hash, "technical_metadata": technical, "exif_metadata": exif, "claimed_metadata": claims, "conflicts": conflicts, "derivative_effects": derivative_effects, "review_required": True, "no_authenticity_determination": True, "no_original_modified": True, "created_at": _utc_now()}
            inspections = [dict(row) for row in _ensure_list(state.get("metadata_inspections"), limit=MAX_EXPORTS)]
            inspections.append(inspection)
            state["metadata_inspections"] = inspections[:MAX_EXPORTS]
            history = _append_history("inspect_media_metadata", "media_metadata", inspection_id, {"media_hash": expected_hash}, {"inspection_sha256": _sha(inspection), "conflict_count": len(conflicts)}, "Inspected bounded local media metadata; metadata did not authenticate the source.")
            self._record_history(state, history)
            self._save_state(state)
            return {"status": "pass", "review_required": True, "inspection": inspection, "source": {"media_id": media_id, "media_hash": expected_hash}, "no_authenticity_determination": True}

    def media_metadata_inspection(self, media_id: str, inspection_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            inspection = next((dict(row) for row in _ensure_list(state.get("metadata_inspections"), limit=MAX_EXPORTS) if str(row.get("media_id") or "") == media_id and str(row.get("inspection_id") or "") == inspection_id), None)
            if inspection is None:
                raise HearingMediaWorkbenchError("metadata_inspection_not_found", "The selected media metadata inspection was not found in this matter.", status_code=404)
            return {"status": "pass", "review_required": True, "inspection": inspection, "source": {"media_id": media_id, "media_hash": inspection.get("media_hash")}, "no_authenticity_determination": True}

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
