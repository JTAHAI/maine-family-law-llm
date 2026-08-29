"""Reviewable local context budgeting without model execution."""

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
from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_TASK_FLOORS = {"research": 2048, "draft": 1792, "review": 1536, "summarization": 1024, "classification": 768}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError("context_budget_id_invalid")
    return result


class ContextBudgetStore:
    schema = "maine_family_law_llm.context_budget.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "context-budgets"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "budgets.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".budgets.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "budgets": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=2 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("context_budget_store_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("context_budget_store_unavailable", 409)
        prior = ""
        for event in state.get("events", []):
            copy = dict(event)
            actual = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != prior or actual != _digest(copy):
                raise IntakeWorkbenchError("context_budget_history_invalid", 409)
            prior = actual
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _event(state: dict[str, Any], budget_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {"event_id": f"budget_evt_{hashlib.sha256((budget_id + _now()).encode()).hexdigest()[:24]}", "at": _now(), "action": "context_budget_created", "budget_id": budget_id, "detail": deepcopy(detail), "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "", "review_required": True}
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _source_refs(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > 48:
            raise IntakeWorkbenchError("context_budget_source_refs_invalid")
        refs = []
        for row in value:
            if not isinstance(row, dict):
                raise IntakeWorkbenchError("context_budget_source_ref_invalid")
            source_id = _id(row.get("source_id"))
            digest = str(row.get("content_sha256") or "").casefold()
            if not _HASH.fullmatch(digest):
                raise IntakeWorkbenchError("context_budget_source_hash_invalid")
            chars = max(0, min(int(row.get("char_count") or 0), 200_000))
            refs.append({"source_id": source_id, "content_sha256": digest, "char_count": chars, "lane": str(row.get("lane") or "unknown")[:64]})
        return refs

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(value)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        budget_id = _id(payload.get("budget_id"))
        task = str(payload.get("task") or "review").strip().casefold()
        if task not in _TASK_FLOORS:
            raise IntakeWorkbenchError("context_budget_task_invalid")
        refs = self._source_refs(payload.get("source_refs"))
        verifier = dict(payload.get("verifier_requirements") or {})
        requirements = {name: bool(verifier.get(name, False)) for name in ("citation", "quote", "claim")}
        profile = profile_hardware(self.root).as_dict()
        available_memory = int(profile.get("available_memory_bytes") or 0)
        hardware_limit = max(512, int(profile.get("recommended_context_limit") or 4096))
        if available_memory and available_memory < 4 * 1024**3:
            hardware_limit = min(hardware_limit, 2048)
        requested = max(0, int(payload.get("requested_context_tokens") or 0))
        source_chars = sum(row["char_count"] for row in refs)
        source_density_tokens = max(256, min(hardware_limit, (source_chars + 3) // 4))
        verifier_reserve = 256 + (512 if requirements["citation"] else 0) + (384 if requirements["quote"] else 0) + (768 if requirements["claim"] else 0)
        task_floor = _TASK_FLOORS[task]
        proposed = max(task_floor, min(source_density_tokens + verifier_reserve, hardware_limit))
        allocation = min(hardware_limit, requested or proposed)
        blockers: list[str] = []
        if requested and requested > hardware_limit:
            blockers.append("requested_context_capped_by_hardware")
        if allocation <= verifier_reserve:
            blockers.append("verifier_reserve_exhausts_context")
        if available_memory and available_memory < 4 * 1024**3:
            blockers.append("low_memory_context_cap_active")
        record = {"budget_id": budget_id, "task": task, "source_refs": refs, "source_density": {"source_count": len(refs), "total_chars": source_chars, "estimated_tokens": source_density_tokens}, "verifier_requirements": requirements, "hardware": {"recommended_context_limit": hardware_limit, "available_memory_bytes": available_memory}, "allocation": {"context_tokens": allocation, "verifier_reserve_tokens": verifier_reserve, "source_content_tokens": max(0, allocation - verifier_reserve), "task_floor_tokens": task_floor}, "blockers": blockers, "status": "allocated_review_required" if not blockers else "allocated_with_limits_review_required", "created_at": _now(), "review_required": True, "local_only": True, "network_used": False}
        with exclusive_file_lock(self.lock):
            state = self._load()
            if budget_id in state["budgets"]:
                raise IntakeWorkbenchError("context_budget_id_exists", 409)
            state["budgets"][budget_id] = record
            event = self._event(state, budget_id, {"task": task, "source_count": len(refs), "context_tokens": allocation})
            self._write(state)
        return {"budget": self._public(record), "receipt": deepcopy(event)}

    def get(self, budget_id: str) -> dict[str, Any]:
        record = self._load()["budgets"].get(_id(budget_id))
        if not record:
            raise IntakeWorkbenchError("context_budget_not_found", 404)
        return {"budget": self._public(record)}

    def source(self, budget_id: str, source_id: str) -> dict[str, Any]:
        record = self._load()["budgets"].get(_id(budget_id))
        if not record:
            raise IntakeWorkbenchError("context_budget_not_found", 404)
        source = next((row for row in record["source_refs"] if row["source_id"] == _id(source_id)), None)
        if not source:
            raise IntakeWorkbenchError("context_budget_source_not_found", 404)
        return {"source_ref": deepcopy(source), "review_required": True}
