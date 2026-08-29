"""Encrypted, matter-scoped persistence for guided-form sessions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_SESSION_ID = re.compile(r"[a-f0-9]{24}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class GuidedFormSessionStore:
    """Persists user-entered working-copy values without exposing a filesystem path."""

    schema = "maine_family_law_llm.guided_form_sessions.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "19_DRAFTING" / "guided-form-sessions"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("guided_form_session_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "sessions.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".sessions.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "sessions": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("guided_form_session_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("sessions", [])
        state.setdefault("ledger", [])
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _id(session_id: str) -> str:
        value = str(session_id or "").strip().casefold()
        if not _SESSION_ID.fullmatch(value):
            raise IntakeWorkbenchError("forms_session_invalid", 409)
        return value

    @staticmethod
    def public(session: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(session)
        result.pop("scope", None)
        result.update({"review_required": True, "filing_ready": False, "local_only": True})
        return result

    def _mutate(self, action: str, session_id: str, callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            state = self._load()
            result = callback(state)
            event = {
                "event_id": f"guided_form_session_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "session_id": session_id,
                "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
            return self.public(result)

    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id = self._id(str(session.get("session_id") or ""))

        def callback(state: dict[str, Any]) -> dict[str, Any]:
            if any(row.get("session_id") == session_id for row in state["sessions"]):
                raise IntakeWorkbenchError("forms_session_already_exists", 409)
            row = deepcopy(session)
            row["session_id"] = session_id
            row["created_at"] = str(row.get("created_at") or _now())
            row["updated_at"] = _now()
            row["review_required"] = True
            row["filing_ready"] = False
            state["sessions"].append(row)
            return row

        return self._mutate("create_guided_form_session", session_id, callback)

    def get(self, session_id: str) -> dict[str, Any]:
        session_id = self._id(session_id)
        session = next((row for row in self._load()["sessions"] if row.get("session_id") == session_id), None)
        if session is None:
            raise IntakeWorkbenchError("forms_session_not_found", 404)
        return self.public(session)

    def replace(self, session: dict[str, Any], *, action: str) -> dict[str, Any]:
        session_id = self._id(str(session.get("session_id") or ""))

        def callback(state: dict[str, Any]) -> dict[str, Any]:
            index = next((idx for idx, row in enumerate(state["sessions"]) if row.get("session_id") == session_id), None)
            if index is None:
                raise IntakeWorkbenchError("forms_session_not_found", 404)
            row = deepcopy(session)
            row["session_id"] = session_id
            row["updated_at"] = _now()
            row["review_required"] = True
            row["filing_ready"] = False
            state["sessions"][index] = row
            return row

        return self._mutate(action, session_id, callback)
