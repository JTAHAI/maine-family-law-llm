"""Encrypted, review-only versioned calendar inputs and business-day receipts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, limit: int = 1_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


def _date(value: Any, field: str) -> str:
    try:
        return date.fromisoformat(str(value or "").strip()).isoformat()
    except ValueError as exc:
        raise IntakeWorkbenchError(f"{field}_invalid") from exc


class BusinessDayReviewStore:
    schema = "maine_family_law_llm.business_day_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "22_CALENDAR_REVIEW" / "business-days"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("business_day_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "business-days.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".business-days.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "inputs": [], "calculations": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("business_day_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("inputs", [])
        state.setdefault("calculations", [])
        state.setdefault("ledger", [])
        state.setdefault("revision", 0)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(row)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "filing_ready": False,
                "local_only": True,
                "deadline_determined": False,
                "notice": "This is a versioned, reviewer-entered calendar input and candidate business-day calculation. It does not establish a court holiday, deadline, jurisdiction, or legal effect.",
            }
        )
        return result

    @staticmethod
    def _authority(raw: dict[str, Any]) -> dict[str, Any]:
        source_hash = str(raw.get("source_hash") or "").casefold()
        if not _HASH.fullmatch(source_hash):
            raise IntakeWorkbenchError("business_day_authority_invalid", 409)
        return {
            "authority_id": _id(raw.get("authority_id"), "business_day_authority_id"),
            "source_id": _text(raw.get("source_id"), "business_day_authority_source_id", 240),
            "source_hash": source_hash,
            "citation": _text(raw.get("citation"), "business_day_authority_citation", 500),
            "title": _text(raw.get("title"), "business_day_authority_title", 500),
            "exact_span": _text(raw.get("exact_span"), "business_day_authority_span", 4_000, False),
            "freshness_status": _text(raw.get("freshness_status"), "business_day_authority_freshness", 80, False) or "unknown",
            "lane": "official_authority",
        }

    @staticmethod
    def _holidays(raw: Any) -> list[str]:
        if not isinstance(raw, list) or len(raw) > 400:
            raise IntakeWorkbenchError("business_day_holidays_invalid")
        values = [_date(item, "business_day_holiday") for item in raw]
        if len(set(values)) != len(values):
            raise IntakeWorkbenchError("business_day_holidays_duplicate")
        return sorted(values)

    def create_input(self, payload: dict[str, Any], *, authority: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("business_day_input_confirmation_required", 409)
        input_id = _id(payload.get("input_id"), "business_day_input_id")
        calendar_key = _id(payload.get("calendar_key"), "business_day_calendar_key")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        valid_from = _date(payload.get("valid_from"), "business_day_valid_from")
        valid_through = _date(payload.get("valid_through"), "business_day_valid_through")
        if valid_through < valid_from:
            raise IntakeWorkbenchError("business_day_validity_invalid")
        entry = {
            "input_id": input_id,
            "calendar_key": calendar_key,
            "version_label": _text(payload.get("version_label"), "business_day_version_label", 160),
            "jurisdiction_label": _text(payload.get("jurisdiction_label"), "business_day_jurisdiction_label", 240),
            "reviewer_safe_id": reviewer,
            "valid_from": valid_from,
            "valid_through": valid_through,
            "holidays": self._holidays(payload.get("holidays") or []),
            "authority": self._authority(authority),
            "created_at": _now(),
            "review_required": True,
            "filing_ready": False,
        }
        entry["input_hash"] = _digest({key: value for key, value in entry.items() if key != "created_at"})
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("input_id") == input_id for row in state["inputs"]):
                raise IntakeWorkbenchError("business_day_input_id_already_exists", 409)
            state["inputs"].append(entry)
            self._append_event(state, "create_business_day_input", input_id)
            self._save(state)
        return self._public(entry)

    @staticmethod
    def _append_event(state: dict[str, Any], action: str, subject_id: str) -> None:
        event = {
            "event_id": f"business_day_{uuid.uuid4().hex}",
            "at": _now(),
            "action": action,
            "subject_id": subject_id,
            "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        state["ledger"].append(event)
        state["revision"] = int(state.get("revision") or 0) + 1

    def inputs(self, input_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["inputs"]]
        if input_id:
            wanted = _id(input_id, "business_day_input_id")
            found = next((row for row in rows if row.get("input_id") == wanted), None)
            if found is None:
                raise IntakeWorkbenchError("business_day_input_not_found", 404)
            return {"input": found, "review_required": True, "local_only": True}
        return {"inputs": rows, "review_required": True, "local_only": True}

    def calculate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("business_day_calculation_confirmation_required", 409)
        calculation_id = _id(payload.get("calculation_id"), "business_day_calculation_id")
        input_id = _id(payload.get("input_id"), "business_day_input_id")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        start = date.fromisoformat(_date(payload.get("start_date"), "business_day_start_date"))
        try:
            offset = int(payload.get("business_days"))
        except (TypeError, ValueError) as exc:
            raise IntakeWorkbenchError("business_day_offset_invalid") from exc
        if offset < 0 or offset > 1_000:
            raise IntakeWorkbenchError("business_day_offset_invalid")
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("calculation_id") == calculation_id for row in state["calculations"]):
                raise IntakeWorkbenchError("business_day_calculation_id_already_exists", 409)
            input_row = next((row for row in state["inputs"] if row.get("input_id") == input_id), None)
            if input_row is None:
                raise IntakeWorkbenchError("business_day_input_not_found", 404)
            if start.isoformat() < str(input_row["valid_from"]) or start.isoformat() > str(input_row["valid_through"]):
                raise IntakeWorkbenchError("business_day_start_outside_input", 409)
            holidays = set(input_row["holidays"])
            current = start
            skipped: list[str] = []
            counted = 0
            while counted < offset:
                current += timedelta(days=1)
                if current.weekday() >= 5 or current.isoformat() in holidays:
                    skipped.append(current.isoformat())
                    continue
                counted += 1
            if current.isoformat() > str(input_row["valid_through"]):
                raise IntakeWorkbenchError("business_day_candidate_outside_input", 409)
            calculation = {
                "calculation_id": calculation_id,
                "input_id": input_id,
                "input_hash": input_row["input_hash"],
                "reviewer_safe_id": reviewer,
                "start_date": start.isoformat(),
                "business_days": offset,
                "candidate_date": current.isoformat(),
                "skipped_non_business_dates": skipped,
                "authority": dict(input_row["authority"]),
                "created_at": _now(),
                "review_required": True,
                "filing_ready": False,
            }
            calculation["receipt_hash"] = _digest({key: value for key, value in calculation.items() if key != "created_at"})
            state["calculations"].append(calculation)
            self._append_event(state, "calculate_business_day_candidate", calculation_id)
            self._save(state)
        return self._public(calculation)

    def calculations(self, calculation_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["calculations"]]
        if calculation_id:
            wanted = _id(calculation_id, "business_day_calculation_id")
            found = next((row for row in rows if row.get("calculation_id") == wanted), None)
            if found is None:
                raise IntakeWorkbenchError("business_day_calculation_not_found", 404)
            return {"calculation": found, "review_required": True, "local_only": True}
        return {"calculations": rows, "review_required": True, "local_only": True}

    def authority_source(self, input_id: str) -> dict[str, Any]:
        entry = self.inputs(input_id)["input"]
        return {"input_id": entry["input_id"], "source": entry["authority"], "review_required": True}
