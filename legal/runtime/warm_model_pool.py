"""Encrypted, pressure-aware lifecycle for explicitly releasable local workers.

The pool never downloads or admits a model.  Its only job is to keep a model
that has already passed the task-admission boundary warm using synthetic text,
then explicitly release it on an operator request or safe pressure signal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_THERMAL_STATES = frozenset({"unknown", "normal", "elevated", "critical"})
_LOW_MEMORY_BYTES = 4 * 1024**3


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_id(value: Any, label: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _ID.fullmatch(candidate):
        raise IntakeWorkbenchError(f"{label}_invalid")
    return candidate


class WarmModelWorker(Protocol):
    @property
    def supports_explicit_release(self) -> bool: ...

    def warm(self) -> dict[str, Any]: ...

    def release(self) -> dict[str, Any]: ...


class WarmModelPoolStore:
    schema = "maine_family_law_llm.warm_model_pool.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "warm-model-pool"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "pool.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".pool.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "workers": {}, "events": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=2 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("warm_model_pool_unavailable", 409) from exc
        if value.get("schema") != self.schema:
            raise IntakeWorkbenchError("warm_model_pool_unavailable", 409)
        self._verify_events(value)
        return value

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> None:
        previous = ""
        for event in state.get("events", []):
            copy = dict(event)
            event_hash = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != previous or event_hash != _digest(copy):
                raise IntakeWorkbenchError("warm_model_pool_history_invalid", 409)
            previous = event_hash

    @staticmethod
    def _event(state: dict[str, Any], action: str, model_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"warm_evt_{hashlib.sha256((action + model_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "model_id": model_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    def _pressure(self, thermal_state: str) -> dict[str, Any]:
        thermal = str(thermal_state or "unknown").strip().casefold()
        if thermal not in _THERMAL_STATES:
            raise IntakeWorkbenchError("warm_model_pool_thermal_state_invalid")
        profile = profile_hardware(self.root).as_dict()
        available = int(profile.get("available_memory_bytes") or 0)
        memory_pressure = bool(available and available < _LOW_MEMORY_BYTES)
        thermal_pressure = thermal in {"elevated", "critical"}
        return {
            "available_memory_bytes": available,
            "memory_pressure": memory_pressure,
            "thermal_state": thermal,
            "thermal_pressure": thermal_pressure,
            "release_required": memory_pressure or thermal_pressure,
            "thermal_measurement": "operator_reported" if thermal != "unknown" else "not_measured",
        }

    @staticmethod
    def _public(worker: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(worker.get(key))
            for key in (
                "model_id",
                "task",
                "status",
                "warmed_at",
                "released_at",
                "release_reason",
                "worker_identity",
                "review_required",
                "local_only",
                "network_used",
            )
        }

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(event.get(key))
            for key in ("event_id", "at", "action", "model_id", "detail", "review_required", "event_hash")
        }

    def warm(
        self,
        payload: dict[str, Any],
        *,
        model: dict[str, Any] | None,
        worker: WarmModelWorker | None,
    ) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("warm_model_pool_confirmation_required", 409)
        task = str(payload.get("task") or "").strip()
        if not task or len(task) > 256:
            raise IntakeWorkbenchError("warm_model_pool_task_invalid")
        thermal = str(payload.get("thermal_state") or "unknown")
        pressure = self._pressure(thermal)
        model_id = _safe_id((model or {}).get("model_id") or "no_admitted_model", "warm_model_pool_model_id")
        with exclusive_file_lock(self.lock):
            state = self._load()
            if pressure["release_required"]:
                event = self._event(
                    state,
                    "warm_refused_under_pressure",
                    model_id,
                    {"task": task, "pressure": pressure},
                )
                self._write(state)
                return {
                    "status": "not_warmed_pressure_review_required",
                    "model_id": model_id,
                    "pressure": pressure,
                    "receipt": self._public_event(event),
                    "review_required": True,
                    "local_only": True,
                    "network_used": False,
                }
            if not model or model.get("installation_status") != "admitted_for_task_review_required":
                event = self._event(
                    state,
                    "warm_refused_no_task_admission",
                    model_id,
                    {"task": task},
                )
                self._write(state)
                return {
                    "status": "not_warmed_no_task_admission_review_required",
                    "model_id": model_id,
                    "receipt": self._public_event(event),
                    "review_required": True,
                    "local_only": True,
                    "network_used": False,
                }
            if worker is None or not bool(getattr(worker, "supports_explicit_release", False)):
                event = self._event(
                    state,
                    "warm_refused_release_capability_missing",
                    model_id,
                    {"task": task},
                )
                self._write(state)
                return {
                    "status": "not_warmed_release_capability_missing_review_required",
                    "model_id": model_id,
                    "receipt": self._public_event(event),
                    "review_required": True,
                    "local_only": True,
                    "network_used": False,
                }
            prior = state["workers"].get(model_id)
            if prior and prior.get("status") == "warm_review_required":
                return {
                    "status": "already_warm_review_required",
                    "worker": self._public(prior),
                    "pressure": pressure,
                    "review_required": True,
                    "local_only": True,
                    "network_used": False,
                }
            try:
                identity = dict(worker.warm() or {})
            except Exception:
                event = self._event(state, "warm_failed", model_id, {"task": task, "safe_code": "local_worker_unavailable"})
                self._write(state)
                return {
                    "status": "not_warmed_worker_unavailable_review_required",
                    "model_id": model_id,
                    "receipt": self._public_event(event),
                    "review_required": True,
                    "local_only": True,
                    "network_used": False,
                }
            record = {
                "model_id": model_id,
                "task": task,
                "status": "warm_review_required",
                "warmed_at": _now(),
                "released_at": "",
                "release_reason": "",
                "worker_identity": {
                    "provider_id": str(identity.get("provider_id") or "local"),
                    "model_id": str(identity.get("model_id") or model_id),
                    "endpoint_class": str(identity.get("endpoint_class") or "loopback"),
                },
                "review_required": True,
                "local_only": True,
                "network_used": False,
            }
            state["workers"][model_id] = record
            event = self._event(state, "worker_warmed", model_id, {"task": task, "pressure": pressure})
            self._write(state)
        return {
            "status": "warm_review_required",
            "worker": self._public(record),
            "pressure": pressure,
            "receipt": self._public_event(event),
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def release(self, payload: dict[str, Any], *, worker: WarmModelWorker | None) -> dict[str, Any]:
        model_id = _safe_id(payload.get("model_id"), "warm_model_pool_model_id")
        reason = str(payload.get("reason") or "operator_requested").strip().casefold()
        if reason not in {"operator_requested", "low_memory", "thermal_pressure", "shutdown"}:
            raise IntakeWorkbenchError("warm_model_pool_release_reason_invalid")
        with exclusive_file_lock(self.lock):
            state = self._load()
            record = state["workers"].get(model_id)
            if not record:
                raise IntakeWorkbenchError("warm_model_pool_worker_not_found", 404)
            if record.get("status") != "warm_review_required":
                return {"status": "already_released_review_required", "worker": self._public(record), "review_required": True}
            if worker is None or not bool(getattr(worker, "supports_explicit_release", False)):
                raise IntakeWorkbenchError("warm_model_pool_release_capability_missing", 409)
            try:
                worker.release()
            except Exception as exc:
                event = self._event(state, "worker_release_failed", model_id, {"reason": reason, "safe_code": "local_worker_release_failed"})
                self._write(state)
                raise IntakeWorkbenchError("warm_model_pool_release_failed", 409) from exc
            record.update({"status": "released_review_required", "released_at": _now(), "release_reason": reason})
            event = self._event(state, "worker_released", model_id, {"reason": reason})
            self._write(state)
        return {
            "status": "released_review_required",
            "worker": self._public(record),
            "receipt": self._public_event(event),
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }

    def status(self, *, thermal_state: str = "unknown") -> dict[str, Any]:
        state = self._load()
        pressure = self._pressure(thermal_state)
        return {
            "schema_version": "warm_model_pool_status_v1",
            "workers": [self._public(row) for row in state.get("workers", {}).values()],
            "pressure": pressure,
            "recent_events": [self._public_event(row) for row in state.get("events", [])[-12:]][::-1],
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }
