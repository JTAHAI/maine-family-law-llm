"""Encrypted local command history with a fail-closed replay boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{1,119}\Z")
_READ = frozenset({"matter_search", "authority_search", "smart_view_run"})
_MUTATION = frozenset({"open_workspace_tab", "create_smart_view", "clear_recent_work"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not _ID.fullmatch(result) or ".." in result or "/" in result or "\\" in result:
        raise IntakeWorkbenchError(f"command_history_{label}_invalid")
    return result


def _query(value: Any) -> str:
    result = " ".join(re.findall(r"[\w.-]+", str(value or "")))[:160]
    if len(result) < 2:
        raise IntakeWorkbenchError("command_history_query_invalid")
    return result


class CommandHistoryStore:
    schema = "maine_family_law_llm.command_history.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "command-history"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "commands.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".commands.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "commands": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=2 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("command_history_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("command_history_unavailable", 409)
        self._verify_events(state)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> None:
        prior = ""
        for event in state.get("events", []):
            copy = dict(event)
            digest = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != prior or digest != _digest(copy):
                raise IntakeWorkbenchError("command_history_invalid", 409)
            prior = digest

    @staticmethod
    def _event(state: dict[str, Any], action: str, command_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"command_{hashlib.sha256((action + command_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "command_id": command_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _parameters(operation: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise IntakeWorkbenchError("command_history_parameters_invalid")
        if operation in {"matter_search", "authority_search"}:
            return {"query": _query(value.get("query"))}
        if operation == "smart_view_run":
            return {"view_id": _id(value.get("view_id"), "view_id")}
        return {"target_id": _id(value.get("target_id"), "target_id")}

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(row.get(key))
            for key in ("command_id", "operation", "kind", "parameters", "created_at", "last_replayed_at", "status", "review_required")
        }

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        command_id = _id(payload.get("command_id"), "id")
        operation = str(payload.get("operation") or "").strip().casefold()
        expected_kind = "read" if operation in _READ else "mutation" if operation in _MUTATION else ""
        if not expected_kind:
            raise IntakeWorkbenchError("command_history_operation_invalid")
        if str(payload.get("kind") or expected_kind).strip().casefold() != expected_kind:
            raise IntakeWorkbenchError("command_history_kind_invalid")
        if expected_kind == "mutation" and payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("command_history_mutation_confirmation_required", 409)
        row = {
            "command_id": command_id,
            "operation": operation,
            "kind": expected_kind,
            "parameters": self._parameters(operation, payload.get("parameters")),
            "created_at": _now(),
            "last_replayed_at": "",
            "status": "recorded_review_required",
            "review_required": True,
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            if command_id in state["commands"]:
                raise IntakeWorkbenchError("command_history_id_exists", 409)
            state["commands"][command_id] = row
            receipt = self._event(state, "command_recorded", command_id, {"operation": operation, "kind": expected_kind})
            self._write(state)
        return {"command": self._public(row), "receipt": deepcopy(receipt), "local_only": True, "network_used": False}

    def list(self) -> dict[str, Any]:
        state = self._load()
        rows = sorted(state.get("commands", {}).values(), key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return {"commands": [self._public(row) for row in rows[:100]], "review_required": True, "local_only": True, "network_used": False}

    def replay(self, command_id: str, *, reconfirmed: bool = False) -> dict[str, Any]:
        safe_id = _id(command_id, "id")
        with exclusive_file_lock(self.lock):
            state = self._load()
            row = state["commands"].get(safe_id)
            if not row:
                raise IntakeWorkbenchError("command_history_not_found", 404)
            if row.get("kind") == "mutation" and not reconfirmed:
                return {"command": self._public(row), "status": "reconfirmation_required", "execute": False, "review_required": True, "local_only": True, "network_used": False}
            row["last_replayed_at"] = _now()
            row["status"] = "safe_read_replay_allowed" if row.get("kind") == "read" else "mutation_replay_reconfirmed_not_executed"
            receipt = self._event(state, "command_replay_requested", safe_id, {"kind": row.get("kind"), "reconfirmed": bool(reconfirmed)})
            self._write(state)
        return {"command": self._public(row), "status": row["status"], "execute": row.get("kind") == "read", "receipt": deepcopy(receipt), "review_required": True, "local_only": True, "network_used": False}
