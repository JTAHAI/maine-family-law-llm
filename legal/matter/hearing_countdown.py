"""Encrypted review-only hearing countdowns from source-bound confirmed dates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_DEFAULT_OFFSETS = (14, 7, 3, 1, 0)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, limit: int = 2_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise IntakeWorkbenchError(f"{field}_invalid") from exc


def _page(value: Any, field: str) -> int:
    try:
        result = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise IntakeWorkbenchError(f"{field}_invalid") from exc
    if result < 0 or result > 100_000:
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


class HearingCountdownStore:
    schema = "maine_family_law_llm.hearing_countdown.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "27_HEARING_PREPARATION" / "countdowns"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("hearing_countdown_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "countdowns.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".countdowns.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "countdowns": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("hearing_countdown_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("countdowns", [])
        state.setdefault("ledger", [])
        state.setdefault("revision", 0)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "filing_ready": False,
                "local_only": True,
                "court_calendar_write": False,
                "notice": "This is a local review countdown from a reviewer-confirmed date and source record. It does not confirm a hearing, create a court reminder, determine a deadline, or establish legal sufficiency.",
            }
        )
        return result

    @staticmethod
    def _records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and _HASH.fullmatch(source_hash):
                result[record_id] = row
        return result

    @staticmethod
    def _offsets(raw: Any) -> list[int]:
        if raw in (None, []):
            return list(_DEFAULT_OFFSETS)
        if not isinstance(raw, list) or not raw or len(raw) > 20:
            raise IntakeWorkbenchError("hearing_countdown_offsets_invalid")
        try:
            offsets = [int(item) for item in raw]
        except (TypeError, ValueError) as exc:
            raise IntakeWorkbenchError("hearing_countdown_offsets_invalid") from exc
        if any(item < 0 or item > 365 for item in offsets) or len(set(offsets)) != len(offsets):
            raise IntakeWorkbenchError("hearing_countdown_offsets_invalid")
        return sorted(offsets, reverse=True)

    @staticmethod
    def _prompts(raw: Any) -> list[str]:
        if not isinstance(raw, list) or len(raw) > 30:
            raise IntakeWorkbenchError("hearing_countdown_prompts_invalid")
        return [_text(item, "hearing_countdown_prompt", 1_000) for item in raw if _text(item, "hearing_countdown_prompt", 1_000, False)]

    def create(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("hearing_countdown_confirmation_required", 409)
        countdown_id = _id(payload.get("countdown_id"), "hearing_countdown_id")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        source = payload.get("notice_source")
        if not isinstance(source, dict):
            raise IntakeWorkbenchError("hearing_countdown_notice_source_invalid")
        record_id = _text(source.get("record_id"), "hearing_countdown_notice_record_id", 160)
        source_hash = str(source.get("source_hash") or "").casefold()
        if not _HASH.fullmatch(source_hash):
            raise IntakeWorkbenchError("hearing_countdown_notice_hash_invalid")
        record = self._records(records).get(record_id)
        if record is None or str(record.get("source_hash") or record.get("sha256") or "").casefold() != source_hash:
            raise IntakeWorkbenchError("hearing_countdown_notice_not_in_active_matter", 404)
        confirmed = _date(payload.get("confirmed_date"), "hearing_countdown_date")
        offsets = self._offsets(payload.get("milestone_offsets"))
        milestones = [
            {
                "milestone_id": f"m{offset}",
                "days_before": offset,
                "candidate_date": (confirmed - timedelta(days=offset)).isoformat(),
                "status": "review_required",
                "reminder_mode": "local_review_prompt_only",
            }
            for offset in offsets
        ]
        entry = {
            "countdown_id": countdown_id,
            "reviewer_safe_id": reviewer,
            "hearing_label": _text(payload.get("hearing_label"), "hearing_countdown_label", 300),
            "confirmed_date": confirmed.isoformat(),
            "notice_source": {
                "record_id": record_id,
                "source_hash": source_hash,
                "title": _text(record.get("title") or record.get("source_locator") or record_id, "hearing_countdown_notice_title", 300),
                "page_number": _page(source.get("page_number") or record.get("page_number") or 0, "hearing_countdown_notice_page"),
                "lane": "private_matter_record",
            },
            "milestones": milestones,
            "missing_proof_prompts": self._prompts(payload.get("missing_proof_prompts") or []),
            "created_at": _now(),
            "review_required": True,
            "filing_ready": False,
        }
        entry["countdown_hash"] = _digest({key: value for key, value in entry.items() if key != "created_at"})
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("countdown_id") == countdown_id for row in state["countdowns"]):
                raise IntakeWorkbenchError("hearing_countdown_id_already_exists", 409)
            state["countdowns"].append(entry)
            event = {
                "event_id": f"hearing_countdown_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "create_hearing_countdown",
                "countdown_id": countdown_id,
                "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return self._public(entry)

    def countdowns(self, countdown_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["countdowns"]]
        if countdown_id:
            wanted = _id(countdown_id, "hearing_countdown_id")
            found = next((row for row in rows if row.get("countdown_id") == wanted), None)
            if found is None:
                raise IntakeWorkbenchError("hearing_countdown_not_found", 404)
            return {"countdown": found, "review_required": True, "local_only": True}
        return {"countdowns": rows, "review_required": True, "local_only": True}

    def source(self, countdown_id: str) -> dict[str, Any]:
        countdown = self.countdowns(countdown_id)["countdown"]
        return {"countdown_id": countdown["countdown_id"], "source": countdown["notice_source"], "review_required": True}
