"""Encrypted, matter-scoped continuity for the local workbench.

The record is intentionally narrow: it is a convenience snapshot of the last
safe work context, not a transcript, authority cache, or factual record.  A
stored source reference contains an immutable record id/hash pair, never a
path or reusable capability.  The API must revalidate it against the active
matter before minting a new short-lived inspection capability.
"""

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

_WORKSPACE_ID = re.compile(r"[a-z][a-z0-9_-]{1,79}\Z")
_RECORD_ID = re.compile(r"[A-Za-z0-9._:-]{1,240}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_LANES = frozenset({"private_matter_record", "official_authority"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _workspace_id(value: Any) -> str:
    result = str(value or "").strip().casefold()
    if not _WORKSPACE_ID.fullmatch(result):
        raise IntakeWorkbenchError("recent_work_workspace_id_invalid")
    return result


def _record_id(value: Any) -> str:
    result = str(value or "").strip()
    if not _RECORD_ID.fullmatch(result) or ".." in result or "/" in result or "\\" in result:
        raise IntakeWorkbenchError("recent_work_record_id_invalid")
    return result


def _hash(value: Any) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError("recent_work_source_hash_invalid")
    return result


class RecentWorkStore:
    """Keep one encrypted restore point per workbench workspace."""

    schema = "maine_family_law_llm.recent_work.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "recent-work"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "restore-points.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".restore-points.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "workspaces": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=512 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("recent_work_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("recent_work_unavailable", 409)
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
                raise IntakeWorkbenchError("recent_work_history_invalid", 409)
            prior = digest

    @staticmethod
    def _event(state: dict[str, Any], action: str, workspace_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"recent_{hashlib.sha256((action + workspace_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "workspace_id": workspace_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _sources(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, list) or len(value) > 24:
            raise IntakeWorkbenchError("recent_work_selected_sources_invalid")
        sources: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for raw in value:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("recent_work_selected_source_invalid")
            lane = str(raw.get("lane") or "").strip().casefold()
            if lane not in _LANES:
                raise IntakeWorkbenchError("recent_work_selected_source_lane_invalid")
            if lane == "private_matter_record":
                row = {
                    "lane": lane,
                    "record_id": _record_id(raw.get("record_id")),
                    "source_hash": _hash(raw.get("source_hash")),
                    "page": max(0, min(int(raw.get("page") or 0), 100_000)),
                }
                key = (lane, f"{row['record_id']}:{row['source_hash']}:{row['page']}")
            else:
                source_id = _record_id(raw.get("source_id"))
                row = {"lane": lane, "source_id": source_id}
                key = (lane, source_id)
            if key not in seen:
                sources.append(row)
                seen.add(key)
        return sources

    @staticmethod
    def _draft(value: Any) -> str:
        draft = str(value or "")
        if len(draft.encode("utf-8")) > 32_000:
            raise IntakeWorkbenchError("recent_work_unsent_draft_too_large", 413)
        return draft

    @staticmethod
    def _public(entry: dict[str, Any], *, include_draft: bool = True) -> dict[str, Any]:
        result = {
            key: deepcopy(entry.get(key))
            for key in (
                "workspace_id", "scroll_position", "selected_sources", "saved_at", "review_required",
                "local_only", "network_used", "status",
            )
        }
        if include_draft:
            result["unsent_draft"] = str(entry.get("unsent_draft") or "")
        else:
            result["has_unsent_draft"] = bool(entry.get("unsent_draft"))
        return result

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _workspace_id(payload.get("workspace_id"))
        scroll_position = max(0, min(int(payload.get("scroll_position") or 0), 100_000_000))
        selected_sources = self._sources(payload.get("selected_sources"))
        unsent_draft = self._draft(payload.get("unsent_draft"))
        entry = {
            "workspace_id": workspace_id,
            "scroll_position": scroll_position,
            "selected_sources": selected_sources,
            "unsent_draft": unsent_draft,
            "saved_at": _now(),
            "review_required": True,
            "local_only": True,
            "network_used": False,
            "status": "restore_available_review_required",
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            state["workspaces"][workspace_id] = entry
            receipt = self._event(
                state,
                "recent_work_saved",
                workspace_id,
                {"source_count": len(selected_sources), "has_unsent_draft": bool(unsent_draft), "scroll_saved": True},
            )
            self._write(state)
        return {"restore_point": self._public(entry, include_draft=False), "receipt": deepcopy(receipt)}

    def get(self, workspace_id: str) -> dict[str, Any]:
        safe_workspace = _workspace_id(workspace_id)
        entry = self._load()["workspaces"].get(safe_workspace)
        if not entry:
            return {
                "restore_point": None,
                "status": "no_restore_point",
                "review_required": True,
                "local_only": True,
                "network_used": False,
            }
        return {
            "restore_point": self._public(entry),
            "status": "restore_available_review_required",
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def clear(self, workspace_id: str) -> dict[str, Any]:
        safe_workspace = _workspace_id(workspace_id)
        with exclusive_file_lock(self.lock):
            state = self._load()
            existed = state["workspaces"].pop(safe_workspace, None) is not None
            receipt = self._event(state, "recent_work_cleared", safe_workspace, {"restore_point_existed": existed})
            self._write(state)
        return {
            "status": "cleared" if existed else "already_clear",
            "receipt": deepcopy(receipt),
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def source(self, workspace_id: str, index: int) -> dict[str, Any]:
        entry = self._load()["workspaces"].get(_workspace_id(workspace_id))
        if not entry:
            raise IntakeWorkbenchError("recent_work_not_found", 404)
        sources = list(entry.get("selected_sources") or [])
        if index < 0 or index >= len(sources):
            raise IntakeWorkbenchError("recent_work_source_not_found", 404)
        return {"source": deepcopy(sources[index]), "review_required": True, "local_only": True, "network_used": False}
