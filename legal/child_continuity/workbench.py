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
from typing import Any

from legal.security.durable_io import atomic_write_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor

SCHEMA_VERSION = "child_continuity_workbench_v1"
WORKSPACE_FOLDER = "19_CHILD_CONTINUITY_WORKBENCH"
MAX_CHILDREN = 500
MAX_EVENTS = 5_000
MAX_SCENARIOS = 500
MAX_CLAIMS = 1_000
MAX_EXPORTS = 500
MAX_HISTORY = 10_000
MAX_TEXT = 10_000
_SAFE_ID_RE = re.compile(r"^(?:child-[a-f0-9]{16,64}|[a-f0-9]{16,64})$")
_LOCK = threading.RLock()


class ChildContinuityError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


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


def _mask_text(value: str, *, visible_prefix: int = 2, visible_suffix: int = 2) -> str:
    text = _safe_text(value, limit=200)
    if not text:
        return ""
    if len(text) <= visible_prefix + visible_suffix:
        return "*" * len(text)
    return f"{text[:visible_prefix]}…{text[-visible_suffix:]}"


def _safe_id(prefix: str, *parts: Any) -> str:
    payload = "\0".join(_safe_text(part, limit=1_000) for part in parts)
    return f"{prefix}-{_sha(payload)[:16]}"


def _ensure_list(value: Any, *, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _source_ref(row: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {}
    for key in ("source_id", "source_class", "source_hash", "source_span", "source_label", "source_title"):
        if row.get(key) is not None:
            ref[key] = row.get(key)
    return ref


def _source_span(payload: dict[str, Any]) -> dict[str, Any] | None:
    span = payload.get("source_span")
    if isinstance(span, dict):
        start = span.get("start")
        end = span.get("end")
        try:
            start_value = int(start)
            end_value = int(end)
        except (TypeError, ValueError):
            return None
        if start_value < 0 or end_value < start_value:
            return None
        result = {"start": start_value, "end": end_value}
        for key in ("source_id", "source_hash", "source_title", "source_class"):
            if span.get(key) is not None:
                result[key] = span.get(key)
        return result
    return None


def _user_entered(payload: dict[str, Any]) -> bool:
    value = payload.get("user_entered")
    return bool(value) if isinstance(value, bool) else False


def _history_entry(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    summary: str,
) -> dict[str, Any]:
    timestamp = datetime.now(UTC)
    return {
        "history_id": _safe_id("hist", action, entity_type, entity_id, secrets.token_hex(4), timestamp.isoformat()),
        "generated_at": _utc_now(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_sha256": _sha(before or {}),
        "after_sha256": _sha(after or {}),
        "summary": summary[:1000],
        "review_required": True,
        "time_ns_hint": int(timestamp.timestamp() * 1_000_000_000),
    }


def _privacy_safe_alias(name: str, child_id: str) -> str:
    return f"Child {child_id[:6].upper()}"


def _safe_path(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts)
    if candidate.exists() and candidate.is_symlink():
        raise ChildContinuityError("workspace_symlink_refused", "A child workspace symlink was refused.", status_code=409)
    return candidate


@dataclass(frozen=True)
class ChildContinuityArtifact:
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


class ChildContinuityStore:
    def __init__(self, case_root: Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.exists() or not self.case_root.is_dir():
            raise ChildContinuityError("case_root_unavailable", "The active case workspace is unavailable.", status_code=409)
        self.root = self.case_root / WORKSPACE_FOLDER
        self.children_dir = self.root / "children"
        self.exports_dir = self.root / "exports"
        self.index_path = self.root / "children-index.json.enc"
        self._lock = threading.RLock()
        self._encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MFL_CHILD_CONTINUITY_KEY") or "child-continuity-local-development-key")
        for folder in (self.root, self.children_dir, self.exports_dir):
            if folder.exists() and folder.is_symlink():
                raise ChildContinuityError("workspace_symlink_refused", "A child workspace symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _default_index(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": self.case_root.name,
            "generated_at": _utc_now(),
            "children": [],
        }

    def _default_child_state(self, child_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": self.case_root.name,
            "child_id": child_id,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "profile": profile,
            "events": [],
            "schedule_scenarios": [],
            "claims": [],
            "continuity_builds": [],
            "exports": [],
            "history": [],
        }

    def _child_dir(self, child_id: str) -> Path:
        if not _SAFE_ID_RE.fullmatch(child_id):
            raise ChildContinuityError("invalid_child_id", "Invalid child ID.", status_code=404)
        return _safe_path(self.children_dir, child_id)

    def _state_path(self, child_id: str) -> Path:
        return self._child_dir(child_id) / "child-workbench.json.enc"

    def _load_encrypted(self, path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return fallback
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._encryptor.decrypt_json(payload)

    def _save_encrypted(self, path: Path, payload: dict[str, Any]) -> None:
        envelope = self._encryptor.encrypt_json(payload)
        atomic_write_bytes(path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))

    def _load_index(self) -> dict[str, Any]:
        return self._load_encrypted(self.index_path, self._default_index())

    def _save_index(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["generated_at"] = _utc_now()
        self._save_encrypted(self.index_path, payload)

    def _load_child_state(self, child_id: str) -> dict[str, Any]:
        state = self._load_encrypted(self._state_path(child_id), {})
        if not state:
            raise ChildContinuityError("child_not_found", "The child profile was not found.", status_code=404)
        return state

    def _save_child_state(self, child_id: str, state: dict[str, Any]) -> None:
        state = dict(state)
        state["updated_at"] = _utc_now()
        self._save_encrypted(self._state_path(child_id), state)
        self._sync_index(child_id, state)

    def _sync_index(self, child_id: str, state: dict[str, Any]) -> None:
        index = self._load_index()
        children: list[dict[str, Any]] = []
        replaced = False
        for row in index.get("children") or []:
            if str(row.get("child_id") or "") == child_id:
                children.append(self._public_child_summary(state))
                replaced = True
            else:
                children.append(dict(row))
        if not replaced and len(children) < MAX_CHILDREN:
            children.append(self._public_child_summary(state))
        index["children"] = sorted(children, key=lambda row: (str(row.get("child_alias") or ""), str(row.get("child_id") or "")))
        self._save_index(index)

    def _public_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        masked = {
            "child_alias": str(profile.get("child_alias") or ""),
            "child_name_masked": _mask_text(str(profile.get("child_name") or "")),
            "date_of_birth_masked": _mask_text(str(profile.get("date_of_birth") or ""), visible_prefix=0, visible_suffix=2),
            "school_name_masked": _mask_text(str(profile.get("school_name") or "")),
            "medical_care_masked": _mask_text(str(profile.get("medical_care") or "")),
            "care_aliases": [str(value)[:80] for value in _ensure_list(profile.get("care_aliases"), limit=10)],
            "transportation_aliases": [str(value)[:80] for value in _ensure_list(profile.get("transportation_aliases"), limit=10)],
            "routine_aliases": [str(value)[:80] for value in _ensure_list(profile.get("routine_aliases"), limit=10)],
            "sensitive_fields_masked": True,
        }
        return masked

    def _public_child_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        profile = dict(state.get("profile") or {})
        return {
            "child_id": str(state.get("child_id") or ""),
            "child_alias": str(profile.get("child_alias") or ""),
            "created_at": str(state.get("created_at") or ""),
            "updated_at": str(state.get("updated_at") or ""),
            "event_count": len(state.get("events") or []),
            "claim_count": len(state.get("claims") or []),
            "scenario_count": len(state.get("schedule_scenarios") or []),
            "export_count": len(state.get("exports") or []),
            "review_required": True,
        }

    def _validate_profile_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        child_name = _safe_text(payload.get("child_name") or payload.get("name"), limit=120)
        if not child_name:
            raise ChildContinuityError("child_name_required", "A child name is required.")
        child_id = _safe_text(payload.get("child_id") or "", limit=64).lower()
        if child_id and not _SAFE_ID_RE.fullmatch(child_id):
            raise ChildContinuityError("invalid_child_id", "Invalid child ID.", status_code=404)
        source_refs = [_source_ref(row) for row in _ensure_list(payload.get("source_refs"), limit=20) if isinstance(row, dict)]
        computed_child_id = child_id or _safe_id("child", self.case_root, child_name, payload.get("date_of_birth") or payload.get("dob"))
        profile = {
            "child_name": child_name,
            "child_id": computed_child_id,
            "child_alias": _safe_text(payload.get("child_alias") or _privacy_safe_alias(child_name, computed_child_id), limit=120),
            "date_of_birth": _safe_text(payload.get("date_of_birth") or payload.get("dob") or "", limit=40),
            "school_name": _safe_text(payload.get("school_name") or "", limit=160),
            "medical_care": _safe_text(payload.get("medical_care") or "", limit=160),
            "school_notes": _safe_text(payload.get("school_notes") or "", limit=400),
            "care_notes": _safe_text(payload.get("care_notes") or "", limit=400),
            "routines_notes": _safe_text(payload.get("routines_notes") or "", limit=400),
            "transportation_notes": _safe_text(payload.get("transportation_notes") or "", limit=400),
            "contact_notes": _safe_text(payload.get("contact_notes") or "", limit=400),
            "source_refs": source_refs,
            "review_required": True,
            "local_only": True,
        }
        return profile

    def list_children(self) -> dict[str, Any]:
        with self._lock:
            index = self._load_index()
            children = list(index.get("children") or [])
            return {
                "schema_version": SCHEMA_VERSION,
                "matter_id": self.case_root.name,
                "status": "pass",
                "review_required": True,
                "local_only": True,
                "generated_at": index.get("generated_at") or _utc_now(),
                "child_count": len(children),
                "children": children,
            }

    def create_child(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            profile = self._validate_profile_payload(payload)
            child_id = str(profile["child_id"])
            child_dir = self._child_dir(child_id)
            child_dir.mkdir(parents=True, exist_ok=True)
            state_path = self._state_path(child_id)
            if state_path.exists():
                raise ChildContinuityError("child_exists", "A child profile with this ID already exists.", status_code=409)
            state = self._default_child_state(child_id, profile)
            state["history"].append(
                _history_entry(
                    action="create",
                    entity_type="child_profile",
                    entity_id=child_id,
                    before=None,
                    after=state.get("profile"),
                    summary="Created a child continuity profile with local-only encrypted storage.",
                )
            )
            self._save_child_state(child_id, state)
            return {
                "status": "pass",
                "review_required": True,
                "local_only": True,
                "child": {
                    "child_id": child_id,
                    "profile": self._public_profile(profile),
                    "summary": self._public_child_summary(state),
                },
            }

    def get_child(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            return self._public_state(state)

    def patch_child(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            before = dict(state.get("profile") or {})
            profile = dict(before)
            for field in (
                "child_alias",
                "child_name",
                "date_of_birth",
                "school_name",
                "medical_care",
                "school_notes",
                "care_notes",
                "routines_notes",
                "transportation_notes",
                "contact_notes",
            ):
                if field in payload:
                    profile[field] = _safe_text(payload.get(field), limit=400)
            if "source_refs" in payload:
                profile["source_refs"] = [_source_ref(row) for row in _ensure_list(payload.get("source_refs"), limit=20) if isinstance(row, dict)]
            profile["review_required"] = True
            profile["local_only"] = True
            state["profile"] = profile
            state["history"].append(
                _history_entry(
                    action="patch",
                    entity_type="child_profile",
                    entity_id=child_id,
                    before=before,
                    after=profile,
                    summary="Updated the child profile with masked, local-only continuity fields.",
                )
            )
            self._save_child_state(child_id, state)
            return self._public_state(state)

    def add_event(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            events = list(state.get("events") or [])
            if len(events) >= MAX_EVENTS:
                raise ChildContinuityError("event_limit_exceeded", "The child event limit was exceeded.", status_code=409)
            event_type = _safe_text(payload.get("event_type") or "", limit=80)
            if not event_type:
                raise ChildContinuityError("event_type_required", "An event type is required.")
            source_span = _source_span(payload)
            if source_span is None and not _user_entered(payload):
                raise ChildContinuityError("source_or_user_entry_required", "Every event must link to a source span or be marked user-entered.")
            event = {
                "event_id": _safe_id("evt", child_id, event_type, len(events), secrets.token_hex(4)),
                "child_id": child_id,
                "event_type": event_type,
                "category": _safe_text(payload.get("category") or event_type, limit=80),
                "label": _safe_text(payload.get("label") or event_type, limit=160),
                "date": _safe_text(payload.get("date") or "", limit=40),
                "status": self._normalize_status(payload),
                "details": _safe_text(payload.get("details") or "", limit=1_500),
                "source_span": source_span,
                "user_entered": _user_entered(payload),
                "review_required": True,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
            if event["status"] == "missed" and "resched" in event["details"].casefold():
                event["status"] = "missed_or_rescheduled"
            if event_type == "appointment" and event["status"] == "scheduled" and "attended" in event["details"].casefold():
                event["status"] = "attended"
            events.append(event)
            state["events"] = events
            state["history"].append(
                _history_entry(
                    action="add",
                    entity_type="child_event",
                    entity_id=event["event_id"],
                    before=None,
                    after=event,
                    summary=f"Added a child continuity event of type {event_type}.",
                )
            )
            self._save_child_state(child_id, state)
            return {"status": "pass", "review_required": True, "event": event, "summary": self._public_child_summary(state)}

    def patch_event(self, child_id: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            events = list(state.get("events") or [])
            for idx, event in enumerate(events):
                if str(event.get("event_id") or "") != event_id:
                    continue
                before = dict(event)
                updated = dict(event)
                for field in ("event_type", "category", "label", "date", "details"):
                    if field in payload:
                        updated[field] = _safe_text(payload.get(field), limit=1_500 if field == "details" else 160)
                if "status" in payload:
                    updated["status"] = self._normalize_status(payload)
                if "source_span" in payload:
                    updated["source_span"] = _source_span(payload)
                if "user_entered" in payload:
                    updated["user_entered"] = _user_entered(payload)
                updated["updated_at"] = _utc_now()
                if updated.get("source_span") is None and not updated.get("user_entered"):
                    raise ChildContinuityError("source_or_user_entry_required", "Every event must link to a source span or be marked user-entered.")
                events[idx] = updated
                state["events"] = events
                state["history"].append(
                    _history_entry(
                        action="patch",
                        entity_type="child_event",
                        entity_id=event_id,
                        before=before,
                        after=updated,
                        summary="Updated a child continuity event while preserving history.",
                    )
                )
                self._save_child_state(child_id, state)
                return {"status": "pass", "review_required": True, "event": updated, "summary": self._public_child_summary(state)}
            raise ChildContinuityError("event_not_found", "The child event was not found.", status_code=404)

    def continuity(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            return self._build_continuity_payload(state, build=False)

    def build_continuity(self, child_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            build = self._build_continuity_payload(state, build=True)
            state["continuity_builds"] = list(state.get("continuity_builds") or [])[-MAX_HISTORY:]
            state["continuity_builds"].append(build)
            state["history"].append(
                _history_entry(
                    action="build",
                    entity_type="continuity_snapshot",
                    entity_id=build["build_id"],
                    before=None,
                    after=build,
                    summary="Built a continuity snapshot for review and export readiness.",
                )
            )
            self._save_child_state(child_id, state)
            return build

    def school(self, child_id: str) -> dict[str, Any]:
        return self._section_payload(child_id, "school")

    def care(self, child_id: str) -> dict[str, Any]:
        return self._section_payload(child_id, "care")

    def services(self, child_id: str) -> dict[str, Any]:
        return self._section_payload(child_id, "services")

    def gaps(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            gaps = self._derive_gaps(state)
            return {
                "schema_version": SCHEMA_VERSION,
                "child_id": child_id,
                "status": "pass",
                "review_required": True,
                "gaps": gaps,
            }

    def build_schedule_scenarios(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            scenarios_payload = [row for row in _ensure_list(payload.get("scenarios"), limit=MAX_SCENARIOS) if isinstance(row, dict)]
            if not scenarios_payload:
                raise ChildContinuityError("scenarios_required", "At least one schedule scenario is required.")
            scenarios = [self._derive_schedule_scenario(state, scenario, index=index) for index, scenario in enumerate(scenarios_payload)]
            record = {
                "scenario_build_id": _safe_id("sched", child_id, len(state.get("schedule_scenarios") or []), _utc_now()),
                "generated_at": _utc_now(),
                "scenarios": scenarios,
                "review_required": True,
                "neutral_schedule_calculation": True,
                "no_custody_score": True,
                "no_parent_ranking": True,
            }
            state["schedule_scenarios"] = list(state.get("schedule_scenarios") or []) + [record]
            state["history"].append(
                _history_entry(
                    action="build",
                    entity_type="schedule_scenario",
                    entity_id=record["scenario_build_id"],
                    before=None,
                    after=record,
                    summary="Built neutral schedule scenarios without custody scoring or parent ranking.",
                )
            )
            self._save_child_state(child_id, state)
            return {"status": "pass", "review_required": True, **record}

    def review_claims(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            claims_payload = [row for row in _ensure_list(payload.get("claims"), limit=MAX_CLAIMS) if isinstance(row, dict)]
            if not claims_payload:
                raise ChildContinuityError("claims_required", "At least one claim is required.")
            claims = [self._review_claim(state, claim, index=index) for index, claim in enumerate(claims_payload)]
            record = {
                "review_id": _safe_id("claim", child_id, len(state.get("claims") or []), _utc_now()),
                "generated_at": _utc_now(),
                "claims": claims,
                "review_required": True,
                "child_impact_lens": True,
                "no_custody_score": True,
                "no_diagnosis": True,
            }
            state["claims"] = list(state.get("claims") or []) + [record]
            state["history"].append(
                _history_entry(
                    action="review",
                    entity_type="claim_review",
                    entity_id=record["review_id"],
                    before=None,
                    after=record,
                    summary="Reviewed claims and contradictions without making custody or diagnosis conclusions.",
                )
            )
            self._save_child_state(child_id, state)
            return {"status": "pass", "review_required": True, **record}

    def packet(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not bool(payload.get("approved")):
                raise ChildContinuityError("explicit_approval_required", "Explicit approval is required to export a child packet.", status_code=409)
            state = self._load_child_state(child_id)
            continuity = self._build_continuity_payload(state, build=False)
            packet = {
                "schema_version": SCHEMA_VERSION,
                "child_id": child_id,
                "matter_id": self.case_root.name,
                "child_alias": str((state.get("profile") or {}).get("child_alias") or ""),
                "generated_at": _utc_now(),
                "review_required": True,
                "local_only": True,
                "masked_profile": self._public_profile(dict(state.get("profile") or {})),
                "continuity": continuity,
                "source_span_required": True,
                "no_custody_score": True,
                "no_diagnosis": True,
                "no_parent_ranking": True,
            }
            packet["packet_sha256"] = _sha(packet)
            build_id = packet["packet_sha256"][:24]
            export_dir = self.exports_dir / build_id
            export_dir.mkdir(parents=True, exist_ok=True)
            report_artifacts = self._export_artifacts(state, packet)
            receipt = {
                "schema_version": "child_continuity_packet_receipt_v1",
                "build_id": build_id,
                "child_id": child_id,
                "packet_sha256": packet["packet_sha256"],
                "generated_at": packet["generated_at"],
                "review_required": True,
            }
            receipt["receipt_sha256"] = _sha(receipt)
            manifest_rows = []
            artifacts = {
                **report_artifacts,
                "child-focused-evidence-packet.json": json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                "child-focused-evidence-packet.txt": self._packet_text(packet).encode("utf-8"),
                "child-continuity-packet.json": json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                "child-continuity-packet.txt": self._packet_text(packet).encode("utf-8"),
                "child-continuity-receipt.json": json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8"),
            }
            receipt["artifact_count"] = len(artifacts)
            receipt["receipt_sha256"] = _sha(receipt)
            for name, raw in artifacts.items():
                atomic_write_bytes(export_dir / name, raw)
                manifest_rows.append({"name": name, "sha256": _sha(raw), "size_bytes": len(raw)})
            manifest = {
                "schema_version": "child_continuity_packet_manifest_v1",
                "build_id": build_id,
                "child_id": child_id,
                "packet_sha256": packet["packet_sha256"],
                "generated_at": packet["generated_at"],
                "files": manifest_rows,
            }
            manifest["manifest_sha256"] = _sha(manifest)
            atomic_write_bytes(export_dir / "child-continuity-manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
            state["exports"] = list(state.get("exports") or []) + [{"build_id": build_id, "packet_sha256": packet["packet_sha256"], "created_at": packet["generated_at"]}]
            state["history"].append(
                _history_entry(
                    action="export",
                    entity_type="child_packet",
                    entity_id=build_id,
                    before=None,
                    after=packet,
                    summary="Exported a review-required child continuity packet and receipt.",
                )
            )
            self._save_child_state(child_id, state)
            artifacts_payload = [
                ChildContinuityArtifact(
                    name=name,
                    relative_path=f"{build_id}/{name}",
                    sha256=_sha(raw),
                    size_bytes=len(raw),
                    media_type="application/json" if name.endswith(".json") else "text/plain",
                ).as_dict()
                for name, raw in artifacts.items()
            ]
            return {
                "status": "pass",
                "review_required": True,
                "build_id": build_id,
                "packet": packet,
                "receipt": receipt,
                "manifest": manifest,
                "artifacts": artifacts_payload,
            }

    def _export_artifacts(self, state: dict[str, Any], packet: dict[str, Any]) -> dict[str, bytes]:
        reports = self._report_payloads(state, packet)
        artifacts: dict[str, bytes] = {}
        for name, payload in reports.items():
            json_bytes = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
            txt_bytes = self._report_text(payload).encode("utf-8")
            artifacts[f"{name}.json"] = json_bytes
            artifacts[f"{name}.txt"] = txt_bytes
        return artifacts

    def _report_payloads(self, state: dict[str, Any], packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
        continuity = dict(packet.get("continuity") or {})
        school = dict(continuity.get("school") or {})
        appointments = dict(continuity.get("appointment_ledger") or {})
        routines = dict(continuity.get("routines") or {})
        transportation = dict(continuity.get("transportation") or {})
        contact = dict(continuity.get("contact") or {})
        gaps = list(continuity.get("gaps") or [])
        claims = list(continuity.get("claims") or [])
        scenarios = list(continuity.get("schedule_scenarios") or [])
        return {
            "child-continuity-summary": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "continuity_summary",
                "child_id": packet.get("child_id"),
                "child_safe_id": packet.get("child_id"),
                "selected_scope": ["continuity", "school", "care", "services", "routines", "transportation", "contact", "appointments", "gaps", "claims", "scenarios"],
                "sources": self._selected_sources(state),
                "missing_records": self._missing_records(state),
                "contradictions": self._claim_contradictions(claims),
                "uncertainties": [gap.get("gap_type") for gap in gaps],
                "review_history": list(continuity.get("review_history") or []),
                "privacy_review": self._privacy_report(state),
                "no_custody_recommendation": True,
                "review_required": True,
            },
            "child-school-history": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "school_history",
                "child_id": packet.get("child_id"),
                "entries": school.get("items") or [],
                "source_ids": self._source_ids(state, section="school"),
                "missing_records": [gap for gap in gaps if "school" in str(gap.get("gap_type") or "")],
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-appointment-service-ledger": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "appointment_service_ledger",
                "child_id": packet.get("child_id"),
                "appointments": appointments.get("items") or [],
                "health_and_care": dict(continuity.get("care") or {}),
                "service_entries": dict(continuity.get("services") or {}),
                "source_ids": self._source_ids(state, section="care", include_services=True),
                "missing_records": [gap for gap in gaps if "appointment" in str(gap.get("gap_type") or "")],
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-routine-history": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "routine_history",
                "child_id": packet.get("child_id"),
                "routines": routines.get("items") or [],
                "source_ids": self._source_ids(state, section="routines"),
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-transportation-report": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "transportation_report",
                "child_id": packet.get("child_id"),
                "transportation": transportation.get("items") or [],
                "source_ids": self._source_ids(state, section="transportation"),
                "missing_records": [gap for gap in gaps if "transportation" in str(gap.get("gap_type") or "")],
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-contact-history": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "contact_history",
                "child_id": packet.get("child_id"),
                "contact": contact.get("items") or [],
                "source_ids": self._source_ids(state, section="contact"),
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-schedule-scenario-comparison": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "schedule_scenario_comparison",
                "child_id": packet.get("child_id"),
                "scenarios": scenarios,
                "selected_scope": ["school_nights", "weekends", "holidays", "exchanges", "transportation", "activity_conflicts", "appointment_conflicts", "sibling_contact", "travel", "transitions_per_week"],
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-continuity-gap-checklist": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "continuity_gap_checklist",
                "child_id": packet.get("child_id"),
                "gaps": gaps,
                "review_required": True,
                "no_custody_recommendation": True,
            },
            "child-impact-claim-report": {
                "schema_version": "child_continuity_export_report_v1",
                "report_kind": "child_impact_claim_review",
                "child_id": packet.get("child_id"),
                "claims": claims,
                "review_required": True,
                "no_custody_recommendation": True,
            },
        }

    def _report_text(self, payload: dict[str, Any]) -> str:
        kind = str(payload.get("report_kind") or "report").replace("_", " ")
        lines = [
            f"Child continuity {kind}",
            f"Child ID: {payload.get('child_id', '')}",
            "Review required.",
            "No custody recommendation, diagnosis, or parent ranking is generated.",
        ]
        for key in ("selected_scope", "source_ids", "missing_records", "contradictions", "uncertainties"):
            value = payload.get(key)
            if value:
                lines.append(f"{key.replace('_', ' ').title()}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        if payload.get("entries") is not None:
            lines.append(f"Entries: {len(payload.get('entries') or [])}")
        if payload.get("appointments") is not None:
            lines.append(f"Appointments: {len(payload.get('appointments') or [])}")
        if payload.get("routines") is not None:
            lines.append(f"Routines: {len(payload.get('routines') or [])}")
        if payload.get("transportation") is not None:
            lines.append(f"Transportation: {len(payload.get('transportation') or [])}")
        if payload.get("contact") is not None:
            lines.append(f"Contact: {len(payload.get('contact') or [])}")
        if payload.get("scenarios") is not None:
            lines.append(f"Scenarios: {len(payload.get('scenarios') or [])}")
        if payload.get("gaps") is not None:
            lines.append(f"Gaps: {len(payload.get('gaps') or [])}")
        if payload.get("claims") is not None:
            lines.append(f"Claims: {len(payload.get('claims') or [])}")
        return "\n".join(lines)

    def _selected_sources(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        profile = dict(state.get("profile") or {})
        source_refs = [dict(row) for row in profile.get("source_refs") or [] if isinstance(row, dict)]
        source_ids = {str(row.get("source_id") or "") for row in source_refs if row.get("source_id")}
        for event in state.get("events") or []:
            span = event.get("source_span")
            if isinstance(span, dict):
                if span.get("source_id"):
                    source_ids.add(str(span.get("source_id")))
        return [{"source_id": source_id} for source_id in sorted(source_ids)]

    def _source_ids(self, state: dict[str, Any], *, section: str, include_services: bool = False) -> list[str]:
        ids: set[str] = set()
        for event in state.get("events") or []:
            category = str(event.get("category") or "").casefold()
            if category == section or (include_services and category in {"care", "services"}):
                span = event.get("source_span")
                if isinstance(span, dict) and span.get("source_id"):
                    ids.add(str(span.get("source_id")))
        return sorted(ids)

    def _missing_records(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        gaps = self._derive_gaps(state)
        return [{"gap_id": gap.get("gap_id"), "gap_type": gap.get("gap_type"), "review_required": True} for gap in gaps]

    def _claim_contradictions(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contradictions: list[dict[str, Any]] = []
        for claim in claims:
            contradictions.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "supporting_event_ids": list(claim.get("supporting_event_ids") or []),
                    "contradicting_event_ids": list(claim.get("contradicting_event_ids") or []),
                    "reviewer_decision": claim.get("reviewer_decision"),
                    "review_required": True,
                }
            )
        return contradictions

    def _privacy_report(self, state: dict[str, Any]) -> dict[str, Any]:
        profile = dict(state.get("profile") or {})
        warnings = []
        if profile.get("child_name"):
            warnings.append("minor_name_masking")
        if profile.get("date_of_birth"):
            warnings.append("dob_masking")
        if profile.get("school_name"):
            warnings.append("school_name_warning")
        if profile.get("medical_care"):
            warnings.append("provider_name_warning")
        if profile.get("medical_care") or any(str(event.get("category") or "").casefold() == "care" for event in state.get("events") or []):
            warnings.append("diagnosis_and_medication_warning")
        if any("address" in str(event.get("details") or "").casefold() for event in state.get("events") or []):
            warnings.append("address_warning")
        return {
            "masked_by_default": True,
            "warnings": sorted(set(warnings)),
            "restricted_export": True,
            "redaction_receipt": True,
            "no_child_text_in_diagnostics": True,
        }

    def _packet_text(self, packet: dict[str, Any]) -> str:
        continuity = dict(packet.get("continuity") or {})
        sections = [
            "Child continuity packet",
            f"Child alias: {packet.get('child_alias', '')}",
            f"Packet hash: {packet.get('packet_sha256', '')}",
            "",
            "This packet is review-required.",
            "It does not determine custody, diagnose a child, or rank caregivers.",
            "",
            "Continuity summary:",
            f"Profile: {json.dumps(packet.get('masked_profile') or {}, sort_keys=True)}",
            f"School items: {len((continuity.get('school') or {}).get('items') or [])}",
            f"Care items: {len((continuity.get('care') or {}).get('items') or [])}",
            f"Service items: {len((continuity.get('services') or {}).get('items') or [])}",
            f"Gaps: {len(continuity.get('gaps') or [])}",
        ]
        return "\n".join(sections)

    def _public_state(self, state: dict[str, Any]) -> dict[str, Any]:
        profile = dict(state.get("profile") or {})
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": self.case_root.name,
            "child_id": str(state.get("child_id") or ""),
            "created_at": str(state.get("created_at") or ""),
            "updated_at": str(state.get("updated_at") or ""),
            "review_required": True,
            "local_only": True,
            "masked_profile": self._public_profile(profile),
            "summary": self._public_child_summary(state),
            "events": [self._mask_event(event) for event in state.get("events") or []],
            "schedule_scenarios": list(state.get("schedule_scenarios") or []),
            "claims": list(state.get("claims") or []),
            "continuity_builds": list(state.get("continuity_builds") or []),
            "exports": list(state.get("exports") or []),
            "history": list(state.get("history") or []),
        }

    def _mask_event(self, event: dict[str, Any]) -> dict[str, Any]:
        masked = dict(event)
        source_span = masked.get("source_span")
        if isinstance(source_span, dict):
            masked["source_span"] = {
                "source_id": source_span.get("source_id"),
                "start": source_span.get("start"),
                "end": source_span.get("end"),
                "source_hash": _mask_text(str(source_span.get("source_hash") or ""), visible_prefix=6, visible_suffix=4),
            }
        return masked

    def _normalize_status(self, payload: dict[str, Any]) -> str:
        status = _safe_text(payload.get("status") or "unknown", limit=80).casefold()
        if status in {"scheduled", "attended", "missed", "cancelled", "changed", "unknown", "blocked", "completed", "done"}:
            return status
        if "resched" in status:
            return "changed"
        if "attend" in status:
            return "attended"
        if "miss" in status:
            return "missed"
        return "unknown"

    def _derive_gaps(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        profile = dict(state.get("profile") or {})
        events = list(state.get("events") or [])
        gaps: list[dict[str, Any]] = []
        if profile.get("school_name") and not any(str(event.get("category") or "").casefold() == "school" for event in events):
            gaps.append({"gap_id": _safe_id("gap", "school", state.get("child_id")), "gap_type": "school_continuity_data_missing", "review_required": True})
        if profile.get("medical_care") and not any(str(event.get("category") or "").casefold() == "medical" for event in events):
            gaps.append({"gap_id": _safe_id("gap", "medical", state.get("child_id")), "gap_type": "medical_continuity_data_missing", "review_required": True})
        if any(str(event.get("event_type") or "").casefold() == "appointment" and str(event.get("status") or "").casefold() in {"scheduled", "missed", "unknown", "missed_or_rescheduled"} for event in events):
            if not any(str(event.get("status") or "").casefold() == "attended" for event in events):
                gaps.append({"gap_id": _safe_id("gap", "appointment", state.get("child_id")), "gap_type": "appointment_outcome_unconfirmed", "review_required": True})
        if any(str(event.get("category") or "").casefold() == "transportation" and str(event.get("status") or "").casefold() in {"blocked", "changed", "unknown"} for event in events):
            gaps.append({"gap_id": _safe_id("gap", "transportation", state.get("child_id")), "gap_type": "transportation_continuity_gap", "review_required": True})
        return gaps

    def _derive_schedule_scenario(self, state: dict[str, Any], scenario: dict[str, Any], *, index: int) -> dict[str, Any]:
        title = _safe_text(scenario.get("title") or f"Scenario {index + 1}", limit=120)
        exchanges = int(scenario.get("exchanges") or scenario.get("handoff_count") or 0)
        commute_minutes = int(scenario.get("commute_minutes") or 0)
        transition_events = len([event for event in state.get("events") or [] if str(event.get("event_type") or "").casefold() in {"appointment", "transportation", "contact"}])
        return {
            "scenario_id": _safe_id("scenario", state.get("child_id"), title, index),
            "title": title,
            "review_required": True,
            "neutral_schedule_calculation": True,
            "no_custody_score": True,
            "no_parent_ranking": True,
            "exchange_count": max(0, exchanges),
            "commute_minutes": max(0, commute_minutes),
            "transition_events": transition_events,
            "continuity_load": max(0, exchanges) + max(0, commute_minutes) + transition_events,
            "notes": _safe_text(scenario.get("notes") or "", limit=500),
        }

    def _review_claim(self, state: dict[str, Any], claim: dict[str, Any], *, index: int) -> dict[str, Any]:
        statement = _safe_text(claim.get("statement") or claim.get("claim") or "", limit=1_500)
        if not statement:
            raise ChildContinuityError("claim_statement_required", "Each claim needs a statement.")
        support_ids = [str(item)[:64] for item in _ensure_list(claim.get("supporting_event_ids"), limit=20)]
        contradiction_ids = [str(item)[:64] for item in _ensure_list(claim.get("contradicting_event_ids"), limit=20)]
        missing_context = [str(item)[:120] for item in _ensure_list(claim.get("missing_context"), limit=20)]
        support_events = [event for event in state.get("events") or [] if str(event.get("event_id") or "") in support_ids]
        contradiction_events = [event for event in state.get("events") or [] if str(event.get("event_id") or "") in contradiction_ids]
        decision = _safe_text(claim.get("reviewer_decision") or "review_required", limit=80)
        if decision not in {"review_required", "needs_more_context", "partially_supported", "supported", "contradicted", "qualified"}:
            decision = "review_required"
        return {
            "claim_id": _safe_id("claim", state.get("child_id"), index, statement),
            "statement": statement,
            "scope": _safe_text(claim.get("scope") or "child_continuity", limit=80),
            "supporting_event_ids": support_ids,
            "contradicting_event_ids": contradiction_ids,
            "supporting_events": [self._mask_event(event) for event in support_events],
            "contradicting_events": [self._mask_event(event) for event in contradiction_events],
            "missing_context": missing_context,
            "qualified_by": [str(item)[:120] for item in _ensure_list(claim.get("qualified_by"), limit=20)],
            "alternatives": [str(item)[:240] for item in _ensure_list(claim.get("alternatives"), limit=20)],
            "reviewer_decision": decision,
            "child_impact_lens": True,
            "no_custody_score": True,
            "no_diagnosis": True,
            "review_required": True,
        }

    def _section_payload(self, child_id: str, section: str) -> dict[str, Any]:
        with self._lock:
            state = self._load_child_state(child_id)
            events = [self._mask_event(event) for event in state.get("events") or [] if str(event.get("category") or "").casefold() == section]
            return {
                "schema_version": SCHEMA_VERSION,
                "child_id": child_id,
                "section": section,
                "review_required": True,
                "local_only": True,
                "items": events,
                "count": len(events),
            }

    def _build_continuity_payload(self, state: dict[str, Any], *, build: bool) -> dict[str, Any]:
        child_id = str(state.get("child_id") or "")
        profile = dict(state.get("profile") or {})
        events = list(state.get("events") or [])
        gaps = self._derive_gaps(state)
        school = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "school"]
        care = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "care"]
        services = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "services"]
        routines = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "routines"]
        transportation = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "transportation"]
        contact = [self._mask_event(event) for event in events if str(event.get("category") or "").casefold() == "contact"]
        appointments = [self._mask_event(event) for event in events if str(event.get("event_type") or "").casefold() == "appointment"]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "child_id": child_id,
            "matter_id": self.case_root.name,
            "generated_at": _utc_now(),
            "review_required": True,
            "local_only": True,
            "build_mode": "snapshot" if build else "current",
            "masked_profile": self._public_profile(profile),
            "school": {"items": school, "count": len(school)},
            "care": {"items": care, "count": len(care)},
            "services": {"items": services, "count": len(services)},
            "routines": {"items": routines, "count": len(routines)},
            "transportation": {"items": transportation, "count": len(transportation)},
            "contact": {"items": contact, "count": len(contact)},
            "appointment_ledger": {"items": appointments, "count": len(appointments)},
            "schedule_scenarios": list(state.get("schedule_scenarios") or []),
            "gaps": gaps,
            "claims": list(state.get("claims") or []),
            "review_history": list(state.get("history") or []),
            "child_focused_packet_ready": bool(state.get("exports")),
            "no_custody_score": True,
            "no_diagnosis": True,
            "no_parent_ranking": True,
        }
        payload["build_id"] = _sha(payload)[:24]
        payload["payload_sha256"] = _sha(payload)
        return payload
