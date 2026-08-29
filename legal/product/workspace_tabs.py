"""Encrypted, active-matter workspace tabs for the local workbench."""

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
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = frozenset({"record", "official_source", "draft", "comparison"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not _ID.fullmatch(result) or ".." in result or "/" in result or "\\" in result:
        raise IntakeWorkbenchError(f"workspace_tabs_{label}_invalid")
    return result


def _hash(value: Any) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError("workspace_tabs_source_hash_invalid")
    return result


def _label(value: Any) -> str:
    result = " ".join(str(value or "").split())[:160]
    if not result or "/" in result or "\\" in result:
        raise IntakeWorkbenchError("workspace_tabs_label_invalid")
    return result


class WorkspaceTabsStore:
    schema = "maine_family_law_llm.workspace_tabs.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "workspace-tabs"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "tabs.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".tabs.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "tabs": {}, "active_tab_id": "", "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=2 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("workspace_tabs_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("workspace_tabs_unavailable", 409)
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
                raise IntakeWorkbenchError("workspace_tabs_history_invalid", 409)
            prior = digest

    @staticmethod
    def _event(state: dict[str, Any], action: str, tab_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"tab_{hashlib.sha256((action + tab_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "tab_id": tab_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _target(kind: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise IntakeWorkbenchError("workspace_tabs_target_invalid")
        if kind == "record":
            return {
                "record_id": _id(value.get("record_id"), "record_id"),
                "source_hash": _hash(value.get("source_hash")),
                "page": max(0, min(int(value.get("page") or 0), 100_000)),
            }
        if kind == "official_source":
            return {"source_id": _id(value.get("source_id"), "source_id")}
        if kind == "draft":
            return {"document_id": _id(value.get("document_id"), "document_id")}
        return {"comparison_id": _id(value.get("comparison_id"), "comparison_id")}

    @staticmethod
    def _public(tab: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(tab.get(key))
            for key in ("tab_id", "kind", "label", "target", "created_at", "last_activated_at", "review_required", "status")
        }

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("workspace_tabs_confirmation_required", 409)
        tab_id = _id(payload.get("tab_id"), "id")
        kind = str(payload.get("kind") or "").strip().casefold()
        if kind not in _KINDS:
            raise IntakeWorkbenchError("workspace_tabs_kind_invalid")
        tab = {
            "tab_id": tab_id,
            "kind": kind,
            "label": _label(payload.get("label")),
            "target": self._target(kind, payload.get("target")),
            "created_at": _now(),
            "last_activated_at": _now(),
            "review_required": True,
            "status": "open_review_required",
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            if tab_id in state["tabs"]:
                raise IntakeWorkbenchError("workspace_tabs_id_exists", 409)
            state["tabs"][tab_id] = tab
            state["active_tab_id"] = tab_id
            receipt = self._event(state, "workspace_tab_opened", tab_id, {"kind": kind})
            self._write(state)
        return {"tab": self._public(tab), "receipt": deepcopy(receipt), "active_tab_id": tab_id}

    def list(self) -> dict[str, Any]:
        state = self._load()
        return {
            "tabs": [self._public(tab) for tab in state.get("tabs", {}).values()],
            "active_tab_id": str(state.get("active_tab_id") or ""),
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def activate(self, tab_id: str) -> dict[str, Any]:
        safe_tab_id = _id(tab_id, "id")
        with exclusive_file_lock(self.lock):
            state = self._load()
            tab = state["tabs"].get(safe_tab_id)
            if not tab:
                raise IntakeWorkbenchError("workspace_tabs_not_found", 404)
            tab["last_activated_at"] = _now()
            state["active_tab_id"] = safe_tab_id
            receipt = self._event(state, "workspace_tab_activated", safe_tab_id, {"kind": tab.get("kind")})
            self._write(state)
        return {"tab": self._public(tab), "receipt": deepcopy(receipt), "active_tab_id": safe_tab_id}

    def close(self, tab_id: str) -> dict[str, Any]:
        safe_tab_id = _id(tab_id, "id")
        with exclusive_file_lock(self.lock):
            state = self._load()
            tab = state["tabs"].pop(safe_tab_id, None)
            if not tab:
                raise IntakeWorkbenchError("workspace_tabs_not_found", 404)
            if state.get("active_tab_id") == safe_tab_id:
                state["active_tab_id"] = next(iter(state["tabs"]), "")
            receipt = self._event(state, "workspace_tab_closed", safe_tab_id, {"kind": tab.get("kind")})
            self._write(state)
        return {
            "status": "closed_review_required",
            "active_tab_id": str(state.get("active_tab_id") or ""),
            "receipt": deepcopy(receipt),
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def target(self, tab_id: str) -> dict[str, Any]:
        tab = self._load()["tabs"].get(_id(tab_id, "id"))
        if not tab:
            raise IntakeWorkbenchError("workspace_tabs_not_found", 404)
        return {"tab": self._public(tab), "target": deepcopy(tab["target"]), "review_required": True, "local_only": True, "network_used": False}
