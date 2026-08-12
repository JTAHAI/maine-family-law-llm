"""A privacy-preserving control plane for the local AI workbench.

This service joins the existing runtime, matter, governance, and workflow
features behind one small state model.  It is intentionally conservative:
model acquisition, network access, destructive file operations, and external
connectors are never silently performed here.  Instead they are represented as
reviewable plans with tamper-evident receipts.
"""

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

from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import DurableIOError, atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import StrictJSONError, strict_json_load_path

_SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_MAX_TEXT = 8_000
_MAX_ITEMS = 250
_PERMISSIONS = frozenset(
    {"read_local_files", "write_workspace", "export_bundle", "calendar", "email", "network"}
)
_AUTOMATION_ACTIONS = frozenset(
    {"classify", "extract", "index", "draft", "review", "create_task", "prepare_packet"}
)
_WORK_ITEM_KINDS = frozenset(
    {"research", "intake", "review", "draft", "deadline", "handoff", "maintenance"}
)
_WORK_ITEM_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
_CONNECTOR_KINDS = frozenset({"calendar", "email", "files", "scanner", "drive", "court_portal"})
_HANDOFF_ROLES = frozenset({"owner", "reviewer", "viewer", "advisor"})
_ARTIFACT_SUFFIXES = frozenset({".gguf", ".onnx", ".bin", ".safetensors"})
_PERFORMANCE_MODES = frozenset({"battery_saver", "balanced", "performance"})
_RELEASE_EVIDENCE_STATUSES = frozenset({"pass", "blocked", "review_required"})
_RELEASE_CONTROLS = frozenset(
    {
        "model_artifacts",
        "backup_restore",
        "source_revalidation",
        "security",
        "privacy",
        "accessibility",
        "legal",
        "operations",
    }
)


class LocalWorkbenchError(ValueError):
    """A safe, client-visible error code for control-plane operations."""

    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_id(value: Any, label: str = "identifier") -> str:
    candidate = str(value or "").strip().casefold()
    if not _SAFE_ID.fullmatch(candidate):
        raise LocalWorkbenchError(f"{label}_invalid")
    return candidate


def _text(value: Any, label: str = "text", *, limit: int = _MAX_TEXT) -> str:
    candidate = str(value or "").strip()
    if len(candidate) > limit:
        raise LocalWorkbenchError(f"{label}_too_long")
    return candidate


def _items(value: Any, label: str = "items") -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > _MAX_ITEMS:
        raise LocalWorkbenchError(f"{label}_invalid")
    return deepcopy(value)


class LocalWorkbenchService:
    """Persistent, encrypted local workbench state for one workspace scope."""

    schema = "maine_family_law_llm.local_workbench.v1"

    def __init__(self, workspace_root: str | Path, *, encryption_key: str | None = None):
        root = Path(workspace_root).expanduser().resolve()
        if root.exists() and root.is_symlink():
            raise LocalWorkbenchError("workspace_symlink_refused", 409)
        root.mkdir(parents=True, exist_ok=True)
        self.workspace_root = root
        self.root = root / "90_LOCAL_WORKBENCH"
        if self.root.exists() and self.root.is_symlink():
            raise LocalWorkbenchError("control_plane_symlink_refused", 409)
        self.state_path = self.root / "state.json.enc"
        self.lock_path = self.root / ".state.lock"
        key = (
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        if (
            os.environ.get("MFL_GA_HARDENING", "").strip() == "1"
            and key == "local-development-key-change-me"
        ):
            raise LocalWorkbenchError("control_plane_production_key_required", 409)
        try:
            self.encryptor = LocalEnvelopeEncryptor(key)
        except ValueError as exc:
            raise LocalWorkbenchError("control_plane_encryption_unavailable", 409) from exc
        self.scope_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scope_id": self.scope_id,
            "created_at": _now(),
            "updated_at": _now(),
            "revision": 0,
            "models": {},
            "artifact_admissions": {},
            "plans": {},
            "automations": {},
            "extensions": {},
            "work_items": {},
            "connectors": {},
            "templates": {},
            "handoffs": {},
            "release_evidence": {},
            "performance_policy": {
                "mode": "balanced",
                "max_concurrent_jobs": 1,
                "max_context_tokens": 4096,
                "memory_budget_ratio": 0.5,
                "pause_background_when_low_memory": True,
            },
            "preferences": {
                "appearance": "system",
                "density": "comfortable",
                "motion": "reduced",
                "reading_level": "plain_language",
                "keyboard_first": True,
                "screen_reader_mode": False,
                "voice_enabled": False,
            },
            "privacy": {
                "network_mode": "local_only",
                "telemetry": "off",
                "portable_exports_require_confirmation": True,
                "external_connectors_enabled": False,
            },
            "sources": {},
            "evaluations": {},
            "events": [],
        }

    def _read(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            envelope = strict_json_load_path(
                self.state_path, max_bytes=8 * 1024 * 1024, require_object=True
            )
            state = self.encryptor.decrypt_json(envelope)
        except (StrictJSONError, DurableIOError, OSError, ValueError) as exc:
            raise LocalWorkbenchError("control_plane_state_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope_id") != self.scope_id:
            raise LocalWorkbenchError("control_plane_scope_invalid", 409)
        defaults = self._default_state()
        for key, value in defaults.items():
            if key not in state:
                state[key] = deepcopy(value)
        state["preferences"] = {**defaults["preferences"], **dict(state.get("preferences") or {})}
        state["privacy"] = {**defaults["privacy"], **dict(state.get("privacy") or {})}
        self._verify_events(state)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now()
        payload = self.encryptor.encrypt_json(state)
        try:
            atomic_write_bytes(self.state_path, _canonical(payload), mode=0o600)
        except DurableIOError as exc:
            raise LocalWorkbenchError("control_plane_write_failed", 409) from exc

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> None:
        previous = ""
        for event in state.get("events", []):
            copy = dict(event)
            event_hash = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash", "") != previous or event_hash != _digest(copy):
                raise LocalWorkbenchError("control_plane_history_invalid", 409)
            previous = event_hash

    def _event(
        self,
        state: dict[str, Any],
        action: str,
        *,
        subject_type: str,
        subject_id: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        events = state.setdefault("events", [])
        previous = str(events[-1].get("event_hash") or "") if events else ""
        event = {
            "event_id": f"evt_{uuid.uuid4().hex}",
            "at": _now(),
            "action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "detail": deepcopy(detail or {}),
            "previous_event_hash": previous,
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": event["event_id"],
            "at": event["at"],
            "action": event["action"],
            "subject_type": event["subject_type"],
            "subject_id": event["subject_id"],
            "detail": deepcopy(event.get("detail") or {}),
            "review_required": bool(event.get("review_required", True)),
            "event_hash": event["event_hash"],
        }

    def readiness(self) -> dict[str, Any]:
        hardware = profile_hardware(self.workspace_root).as_dict()
        memory = int(hardware.get("available_memory_bytes") or 0)
        free_disk = int(hardware.get("disk_free_bytes") or 0)
        gpu_or_npu = bool(hardware.get("gpu_hint") or hardware.get("vram_bytes"))
        if memory and memory < 4 * 1024**3:
            tier, mode = "essential", "compact_cpu"
        elif memory and memory < 8 * 1024**3:
            tier, mode = "baseline", "efficient_cpu"
        elif gpu_or_npu:
            tier, mode = "accelerated", "hardware_preferred"
        else:
            tier, mode = "standard", "balanced_cpu"
        blockers: list[str] = []
        if free_disk and free_disk < 4 * 1024**3:
            blockers.append("insufficient_free_disk_for_safe_model_operations")
        return {
            "schema_version": "local_workbench_readiness_v1",
            "tier": tier,
            "recommended_mode": mode,
            "cpu_baseline_supported": not blockers,
            "accelerator_detected": gpu_or_npu,
            "hardware": hardware,
            "blockers": blockers,
            "recommendations": [
                "Keep one compact local model available for offline fallback.",
                "Use acceleration when present, but retain CPU fallback for every core workflow.",
            ],
            "network_used": False,
            "review_required": False,
        }

    def status(self) -> dict[str, Any]:
        state = self._read()
        plans = list(state["plans"].values())
        events = state.get("events", [])
        return {
            "schema_version": "local_workbench_status_v1",
            "scope_id": self.scope_id,
            "readiness": self.readiness(),
            "model_count": len(state["models"]),
            "verified_artifact_count": len(state["artifact_admissions"]),
            "plan_counts": {
                status: sum(1 for plan in plans if plan.get("status") == status)
                for status in ("proposed", "approved", "completed", "cancelled")
            },
            "automation_count": len(state["automations"]),
            "extension_count": len(state["extensions"]),
            "open_work_item_count": sum(
                1 for item in state["work_items"].values() if item.get("status") == "open"
            ),
            "connector_count": len(state["connectors"]),
            "template_count": len(state["templates"]),
            "handoff_count": len(state["handoffs"]),
            "source_snapshot_count": len(state["sources"]),
            "evaluation_count": len(state["evaluations"]),
            "performance_policy": deepcopy(state["performance_policy"]),
            "release_evidence_count": len(state["release_evidence"]),
            "preferences": deepcopy(state["preferences"]),
            "privacy": deepcopy(state["privacy"]),
            "recent_events": [self._public_event(event) for event in events[-12:]][::-1],
            "local_only_by_default": True,
            "network_used": False,
            "review_required": True,
        }

    def register_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_id = _safe_id(payload.get("model_id"), "model_id")
        record = {
            "model_id": model_id,
            "display_name": _text(
                payload.get("display_name") or model_id, "display_name", limit=128
            ),
            "role": _text(payload.get("role") or "general_assistant", "role", limit=128),
            "version": _text(payload.get("version") or "unknown", "version", limit=128),
            "quantization": _text(payload.get("quantization"), "quantization", limit=128),
            "artifact_sha256": _text(
                payload.get("artifact_sha256"), "artifact_sha256", limit=128
            ).casefold(),
            "artifact_size_bytes": max(0, int(payload.get("artifact_size_bytes") or 0)),
            "min_ram_bytes": max(0, int(payload.get("min_ram_bytes") or 0)),
            "min_vram_bytes": max(0, int(payload.get("min_vram_bytes") or 0)),
            "context_limit_tokens": max(0, int(payload.get("context_limit_tokens") or 0)),
            "privacy_status": "local_only",
            "installation_status": "registered_review_required",
            "network_access": "not_granted",
            "created_at": _now(),
        }
        if record["artifact_sha256"] and not re.fullmatch(
            r"[0-9a-f]{64}", record["artifact_sha256"]
        ):
            raise LocalWorkbenchError("artifact_sha256_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            state["models"][model_id] = record
            event = self._event(
                state,
                "model_registered",
                subject_type="model",
                subject_id=model_id,
                detail={"role": record["role"], "version": record["version"]},
            )
            self._write(state)
        return {**deepcopy(record), "receipt": self._public_event(event), "review_required": True}

    def admit_local_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Verify an operator-provided artifact under an external model root.

        This is an admission check, not a downloader or a model executor. A
        caller supplies only a safe filename; the configured external root is
        never returned to the client.
        """

        model_id = _safe_id(payload.get("model_id"), "model_id")
        filename = Path(_text(payload.get("filename"), "artifact_filename", limit=256))
        if (
            not filename.name
            or filename.name != str(filename)
            or filename.suffix.casefold() not in _ARTIFACT_SUFFIXES
        ):
            raise LocalWorkbenchError("artifact_filename_invalid")
        configured = os.environ.get("MFL_MODEL_ARTIFACT_ROOT", "").strip()
        if not configured:
            raise LocalWorkbenchError("model_artifact_root_not_configured", 409)
        root = Path(configured).expanduser().resolve()
        if not root.is_dir() or root.is_symlink():
            raise LocalWorkbenchError("model_artifact_root_unavailable", 409)
        path = (root / filename).resolve()
        if root not in path.parents or not path.is_file() or path.is_symlink():
            raise LocalWorkbenchError("model_artifact_unavailable", 404)
        expected_sha = _text(
            payload.get("expected_sha256"), "expected_sha256", limit=128
        ).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise LocalWorkbenchError("artifact_sha256_invalid")
        actual_sha = hashlib.sha256()
        total_bytes = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > 32 * 1024**3:
                    raise LocalWorkbenchError("artifact_size_limit_exceeded", 413)
                actual_sha.update(chunk)
        if actual_sha.hexdigest() != expected_sha:
            raise LocalWorkbenchError("artifact_sha256_mismatch", 409)
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            model = state["models"].get(model_id)
            if not model:
                raise LocalWorkbenchError("model_not_found", 404)
            registered_sha = str(model.get("artifact_sha256") or "")
            if registered_sha and registered_sha != expected_sha:
                raise LocalWorkbenchError("artifact_sha256_disagrees_with_model_record", 409)
            admission = {
                "model_id": model_id,
                "filename": filename.name,
                "artifact_sha256": expected_sha,
                "artifact_size_bytes": total_bytes,
                "verified_at": _now(),
                "status": "verified_local_artifact_review_required",
                "network_used": False,
            }
            state["artifact_admissions"][model_id] = admission
            model.update(
                {
                    "artifact_sha256": expected_sha,
                    "artifact_size_bytes": total_bytes,
                    "installation_status": "verified_local_artifact_review_required",
                    "artifact_filename": filename.name,
                }
            )
            event = self._event(
                state,
                "local_artifact_verified",
                subject_type="model",
                subject_id=model_id,
                detail={"artifact_size_bytes": total_bytes},
            )
            self._write(state)
        return {**deepcopy(admission), "receipt": self._public_event(event)}

    def configure_performance_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = _text(payload.get("mode") or "balanced", "performance_mode", limit=64)
        if mode not in _PERFORMANCE_MODES:
            raise LocalWorkbenchError("performance_mode_invalid")
        readiness = self.readiness()
        maximum_context = int(readiness["hardware"].get("recommended_context_limit") or 4096)
        requested_context = int(payload.get("max_context_tokens") or maximum_context)
        requested_jobs = int(payload.get("max_concurrent_jobs") or 1)
        budget = float(payload.get("memory_budget_ratio") or 0.5)
        if requested_context < 256 or requested_context > maximum_context:
            raise LocalWorkbenchError("performance_context_limit_invalid")
        if requested_jobs < 1 or requested_jobs > int(
            readiness["hardware"].get("recommended_concurrency") or 1
        ):
            raise LocalWorkbenchError("performance_concurrency_invalid")
        if not 0.2 <= budget <= 0.7:
            raise LocalWorkbenchError("performance_memory_budget_invalid")
        policy = {
            "mode": mode,
            "max_concurrent_jobs": requested_jobs,
            "max_context_tokens": requested_context,
            "memory_budget_ratio": budget,
            "pause_background_when_low_memory": bool(
                payload.get("pause_background_when_low_memory", True)
            ),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            state["performance_policy"] = policy
            event = self._event(
                state,
                "performance_policy_configured",
                subject_type="workspace",
                subject_id=self.scope_id,
                detail={"mode": mode, "max_concurrent_jobs": requested_jobs},
            )
            self._write(state)
        return {
            "policy": deepcopy(policy),
            "receipt": self._public_event(event),
            "network_used": False,
        }

    def preflight_local_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = _text(payload.get("task"), "task", limit=256)
        if not task:
            raise LocalWorkbenchError("task_required")
        state = self._read()
        policy = state["performance_policy"]
        readiness = self.readiness()
        requested_context = int(payload.get("context_tokens") or policy["max_context_tokens"])
        estimated_memory = max(0, int(payload.get("estimated_memory_bytes") or 0))
        available = int(readiness["hardware"].get("available_memory_bytes") or 0)
        budget = int(available * float(policy["memory_budget_ratio"])) if available else 0
        blockers: list[str] = []
        if requested_context > int(policy["max_context_tokens"]):
            blockers.append("requested_context_exceeds_policy")
        if budget and estimated_memory > budget:
            blockers.append("estimated_memory_exceeds_policy_budget")
        return {
            "schema_version": "local_workbench_job_preflight_v1",
            "task": task,
            "status": "ready" if not blockers else "queue_or_reduce_required",
            "policy": deepcopy(policy),
            "estimated_memory_bytes": estimated_memory,
            "memory_budget_bytes": budget,
            "blockers": blockers,
            "network_used": False,
            "review_required": True,
        }

    def route_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = _text(payload.get("task"), "task", limit=256)
        if not task:
            raise LocalWorkbenchError("task_required")
        state = self._read()
        readiness = self.readiness()
        available_memory = int(readiness["hardware"].get("available_memory_bytes") or 0)
        vram = int(readiness["hardware"].get("vram_bytes") or 0)
        compatible = [
            record
            for record in state["models"].values()
            if int(record.get("min_ram_bytes") or 0) <= available_memory
            and int(record.get("min_vram_bytes") or 0) <= vram
        ]
        preferred = _text(
            payload.get("preferred_model_id"), "preferred_model_id", limit=80
        ).casefold()
        if preferred:
            compatible = [record for record in compatible if record["model_id"] == preferred]
        compatible.sort(
            key=lambda item: (
                int(item.get("min_vram_bytes") or 0) > 0,
                int(item.get("context_limit_tokens") or 0),
            ),
            reverse=True,
        )
        chosen = compatible[0] if compatible else None
        return {
            "schema_version": "local_workbench_route_v1",
            "task": task,
            "selected_model": deepcopy(chosen) if chosen else None,
            "status": "ready" if chosen else "cpu_fallback_or_review_required",
            "fallback": "deterministic_or_existing_local_agent_runtime",
            "compatible_model_ids": [item["model_id"] for item in compatible],
            "readiness_tier": readiness["tier"],
            "network_used": False,
            "review_required": True,
        }

    def propose_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = _safe_id(payload.get("plan_id") or f"plan_{uuid.uuid4().hex[:16]}", "plan_id")
        title = _text(payload.get("title"), "title", limit=256)
        if not title:
            raise LocalWorkbenchError("plan_title_required")
        actions = []
        for item in _items(payload.get("actions"), "actions"):
            if not isinstance(item, dict):
                raise LocalWorkbenchError("plan_action_invalid")
            action_id = _safe_id(item.get("action_id"), "action_id")
            operation = _text(item.get("operation"), "operation", limit=128)
            if not operation:
                raise LocalWorkbenchError("plan_operation_required")
            permissions = [
                _text(permission, "permission", limit=64)
                for permission in _items(item.get("permissions"), "permissions")
            ]
            if any(permission not in _PERMISSIONS for permission in permissions):
                raise LocalWorkbenchError("plan_permission_invalid")
            actions.append(
                {
                    "action_id": action_id,
                    "operation": operation,
                    "summary": _text(item.get("summary"), "action_summary", limit=1_000),
                    "permissions": sorted(set(permissions)),
                    "reversible": bool(item.get("reversible", True)),
                    "execution_route": _text(
                        item.get("execution_route"), "execution_route", limit=256
                    ),
                }
            )
        if not actions:
            raise LocalWorkbenchError("plan_actions_required")
        if len({item["action_id"] for item in actions}) != len(actions):
            raise LocalWorkbenchError("plan_action_id_duplicate")
        plan = {
            "plan_id": plan_id,
            "title": title,
            "objective": _text(payload.get("objective"), "objective", limit=2_000),
            "status": "proposed",
            "actions": actions,
            "created_at": _now(),
            "approved_at": "",
            "completed_at": "",
            "requires_confirmation": True,
            "network_permission_requested": any(
                "network" in item["permissions"] for item in actions
            ),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if plan_id in state["plans"]:
                raise LocalWorkbenchError("plan_already_exists", 409)
            state["plans"][plan_id] = plan
            event = self._event(
                state,
                "plan_proposed",
                subject_type="plan",
                subject_id=plan_id,
                detail={"action_count": len(actions)},
            )
            self._write(state)
        return {**deepcopy(plan), "receipt": self._public_event(event)}

    def approve_plan(self, plan_id: str) -> dict[str, Any]:
        plan_id = _safe_id(plan_id, "plan_id")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            plan = state["plans"].get(plan_id)
            if not plan:
                raise LocalWorkbenchError("plan_not_found", 404)
            if plan["status"] != "proposed":
                raise LocalWorkbenchError("plan_not_approvable", 409)
            plan["status"] = "approved"
            plan["approved_at"] = _now()
            event = self._event(
                state,
                "plan_approved",
                subject_type="plan",
                subject_id=plan_id,
                detail={"network_permission_requested": plan["network_permission_requested"]},
            )
            self._write(state)
        return {
            **deepcopy(plan),
            "receipt": self._public_event(event),
            "execution_not_automatic": True,
        }

    def set_preferences(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "appearance",
            "density",
            "motion",
            "reading_level",
            "keyboard_first",
            "screen_reader_mode",
            "voice_enabled",
        }
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise LocalWorkbenchError("preferences_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            for key, value in patch.items():
                state["preferences"][key] = (
                    bool(value)
                    if key in {"keyboard_first", "screen_reader_mode", "voice_enabled"}
                    else _text(value, key, limit=64)
                )
            event = self._event(
                state,
                "preferences_updated",
                subject_type="workspace",
                subject_id=self.scope_id,
                detail={"changed": sorted(patch)},
            )
            self._write(state)
        return {"preferences": deepcopy(state["preferences"]), "receipt": self._public_event(event)}

    def set_privacy(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "network_mode",
            "telemetry",
            "portable_exports_require_confirmation",
            "external_connectors_enabled",
        }
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise LocalWorkbenchError("privacy_settings_invalid")
        if patch.get("network_mode") not in (None, "local_only", "reviewed_opt_in"):
            raise LocalWorkbenchError("network_mode_invalid")
        if patch.get("telemetry") not in (None, "off", "local_only", "redacted_opt_in"):
            raise LocalWorkbenchError("telemetry_mode_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            for key, value in patch.items():
                state["privacy"][key] = (
                    bool(value)
                    if key.endswith("enabled") or key.endswith("confirmation")
                    else str(value)
                )
            event = self._event(
                state,
                "privacy_updated",
                subject_type="workspace",
                subject_id=self.scope_id,
                detail={"changed": sorted(patch)},
            )
            self._write(state)
        return {
            "privacy": deepcopy(state["privacy"]),
            "receipt": self._public_event(event),
            "network_used": False,
        }

    def create_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
        automation_id = _safe_id(payload.get("automation_id"), "automation_id")
        steps = []
        for raw in _items(payload.get("steps"), "automation_steps"):
            if not isinstance(raw, dict):
                raise LocalWorkbenchError("automation_step_invalid")
            action = _text(raw.get("action"), "automation_action", limit=64)
            if action not in _AUTOMATION_ACTIONS:
                raise LocalWorkbenchError("automation_action_not_allowed")
            steps.append(
                {
                    "action": action,
                    "summary": _text(raw.get("summary"), "automation_summary", limit=1_000),
                }
            )
        if not steps:
            raise LocalWorkbenchError("automation_steps_required")
        automation = {
            "automation_id": automation_id,
            "title": _text(payload.get("title"), "automation_title", limit=256),
            "steps": steps,
            "enabled": False,
            "approval_required_every_run": True,
            "created_at": _now(),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if automation_id in state["automations"]:
                raise LocalWorkbenchError("automation_already_exists", 409)
            state["automations"][automation_id] = automation
            event = self._event(
                state,
                "automation_created",
                subject_type="automation",
                subject_id=automation_id,
                detail={"step_count": len(steps)},
            )
            self._write(state)
        return {**deepcopy(automation), "receipt": self._public_event(event)}

    def propose_automation_run(self, automation_id: str) -> dict[str, Any]:
        automation_id = _safe_id(automation_id, "automation_id")
        state = self._read()
        automation = state["automations"].get(automation_id)
        if not automation:
            raise LocalWorkbenchError("automation_not_found", 404)
        return self.propose_plan(
            {
                "plan_id": f"run_{automation_id}_{uuid.uuid4().hex[:12]}",
                "title": f"Run {automation.get('title') or automation_id}",
                "objective": "Reviewable local automation run.",
                "actions": [
                    {
                        "action_id": f"step_{index + 1}_{step['action']}",
                        "operation": step["action"],
                        "summary": step["summary"],
                        "permissions": ["write_workspace"],
                        "reversible": True,
                    }
                    for index, step in enumerate(automation["steps"])
                ],
            }
        )

    def register_extension(self, payload: dict[str, Any]) -> dict[str, Any]:
        extension_id = _safe_id(payload.get("extension_id"), "extension_id")
        permissions = [
            _text(value, "extension_permission", limit=64)
            for value in _items(payload.get("permissions"), "extension_permissions")
        ]
        if any(value not in _PERMISSIONS - {"network"} for value in permissions):
            raise LocalWorkbenchError("extension_permission_invalid")
        extension = {
            "extension_id": extension_id,
            "name": _text(payload.get("name") or extension_id, "extension_name", limit=128),
            "version": _text(payload.get("version") or "0.0.0", "extension_version", limit=64),
            "permissions": sorted(set(permissions)),
            "manifest_sha256": _text(
                payload.get("manifest_sha256"), "manifest_sha256", limit=128
            ).casefold(),
            "status": "review_pending",
            "enabled": False,
            "created_at": _now(),
        }
        if extension["manifest_sha256"] and not re.fullmatch(
            r"[0-9a-f]{64}", extension["manifest_sha256"]
        ):
            raise LocalWorkbenchError("extension_manifest_sha256_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            state["extensions"][extension_id] = extension
            event = self._event(
                state,
                "extension_registered",
                subject_type="extension",
                subject_id=extension_id,
                detail={"permission_count": len(permissions)},
            )
            self._write(state)
        return {
            **deepcopy(extension),
            "receipt": self._public_event(event),
            "execution_enabled": False,
        }

    def create_work_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        work_item_id = _safe_id(payload.get("work_item_id"), "work_item_id")
        kind = _text(payload.get("kind") or "review", "work_item_kind", limit=64)
        priority = _text(payload.get("priority") or "normal", "work_item_priority", limit=32)
        if kind not in _WORK_ITEM_KINDS or priority not in _WORK_ITEM_PRIORITIES:
            raise LocalWorkbenchError("work_item_classification_invalid")
        source_ids = [
            _safe_id(value, "source_id")
            for value in _items(payload.get("source_ids"), "source_ids")
        ]
        item = {
            "work_item_id": work_item_id,
            "title": _text(payload.get("title"), "work_item_title", limit=256),
            "kind": kind,
            "priority": priority,
            "status": "open",
            "due_on": _text(payload.get("due_on"), "due_on", limit=32),
            "source_ids": sorted(set(source_ids)),
            "created_at": _now(),
            "review_required": True,
        }
        if not item["title"]:
            raise LocalWorkbenchError("work_item_title_required")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if work_item_id in state["work_items"]:
                raise LocalWorkbenchError("work_item_already_exists", 409)
            state["work_items"][work_item_id] = item
            event = self._event(
                state,
                "work_item_created",
                subject_type="work_item",
                subject_id=work_item_id,
                detail={"kind": kind, "priority": priority},
            )
            self._write(state)
        return {**deepcopy(item), "receipt": self._public_event(event)}

    def snapshot_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_id = _safe_id(payload.get("source_id"), "source_id")
        content_hash = _text(payload.get("content_sha256"), "content_sha256", limit=128).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
            raise LocalWorkbenchError("source_content_sha256_invalid")
        snapshot = {
            "source_id": source_id,
            "label": _text(payload.get("label") or source_id, "source_label", limit=256),
            "version": _text(payload.get("version") or "unknown", "source_version", limit=128),
            "content_sha256": content_hash,
            "observed_at": _text(payload.get("observed_at") or _now(), "observed_at", limit=64),
            "status": "review_required",
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            prior = state["sources"].get(source_id)
            snapshot["changed_since_prior"] = bool(
                prior and prior.get("content_sha256") != content_hash
            )
            state["sources"][source_id] = snapshot
            event = self._event(
                state,
                "source_snapshot_recorded",
                subject_type="source",
                subject_id=source_id,
                detail={
                    "changed_since_prior": snapshot["changed_since_prior"],
                    "version": snapshot["version"],
                },
            )
            self._write(state)
        return {**deepcopy(snapshot), "receipt": self._public_event(event)}

    def route_source_change(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Turn verified source changes into explicit local review work."""

        changes = _items(payload.get("changes"), "source_changes")
        if not changes:
            raise LocalWorkbenchError("source_changes_required")
        accepted = {"added", "removed", "content_hash_changed", "metadata_changed"}
        created: list[dict[str, Any]] = []
        skipped: list[str] = []
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            for raw in changes:
                if not isinstance(raw, dict):
                    raise LocalWorkbenchError("source_change_invalid")
                source_id = _safe_id(raw.get("source_id"), "source_id")
                change_type = _text(raw.get("change_type"), "source_change_type", limit=64)
                if change_type not in accepted:
                    raise LocalWorkbenchError("source_change_type_invalid")
                existing = next(
                    (
                        item
                        for item in state["work_items"].values()
                        if item.get("status") == "open"
                        and source_id in item.get("source_ids", [])
                        and item.get("kind") == "review"
                    ),
                    None,
                )
                if existing:
                    skipped.append(source_id)
                    continue
                work_item_id = f"source_review_{uuid.uuid4().hex[:16]}"
                item = {
                    "work_item_id": work_item_id,
                    "title": f"Review changed source: {source_id}",
                    "kind": "review",
                    "priority": "high"
                    if change_type in {"removed", "content_hash_changed"}
                    else "normal",
                    "status": "open",
                    "due_on": "",
                    "source_ids": [source_id],
                    "source_change_type": change_type,
                    "created_at": _now(),
                    "review_required": True,
                }
                state["work_items"][work_item_id] = item
                created.append(deepcopy(item))
            event = self._event(
                state,
                "source_change_routed_to_review",
                subject_type="source_change_batch",
                subject_id=f"batch_{uuid.uuid4().hex[:16]}",
                detail={"created_count": len(created), "existing_open_review_count": len(skipped)},
            )
            self._write(state)
        return {
            "created_work_items": created,
            "skipped_source_ids": sorted(skipped),
            "notice": "Source changes create review work; they do not establish a legal effect.",
            "receipt": self._public_event(event),
            "review_required": True,
        }

    def register_connector(self, payload: dict[str, Any]) -> dict[str, Any]:
        connector_id = _safe_id(payload.get("connector_id"), "connector_id")
        kind = _text(payload.get("kind"), "connector_kind", limit=64)
        if kind not in _CONNECTOR_KINDS:
            raise LocalWorkbenchError("connector_kind_invalid")
        connector = {
            "connector_id": connector_id,
            "kind": kind,
            "label": _text(payload.get("label") or connector_id, "connector_label", limit=128),
            "status": "review_pending",
            "enabled": False,
            "credential_storage": "not_configured",
            "network_access": "not_granted",
            "created_at": _now(),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if connector_id in state["connectors"]:
                raise LocalWorkbenchError("connector_already_exists", 409)
            state["connectors"][connector_id] = connector
            event = self._event(
                state,
                "connector_registered",
                subject_type="connector",
                subject_id=connector_id,
                detail={"kind": kind},
            )
            self._write(state)
        return {**deepcopy(connector), "receipt": self._public_event(event)}

    def register_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        template_id = _safe_id(payload.get("template_id"), "template_id")
        template = {
            "template_id": template_id,
            "title": _text(payload.get("title"), "template_title", limit=256),
            "category": _text(
                payload.get("category") or "workflow", "template_category", limit=128
            ),
            "description": _text(payload.get("description"), "template_description", limit=2_000),
            "steps": [
                _text(value, "template_step", limit=512)
                for value in _items(payload.get("steps"), "template_steps")
            ],
            "status": "local_reviewed_template",
            "created_at": _now(),
        }
        if not template["title"] or not template["steps"]:
            raise LocalWorkbenchError("template_title_and_steps_required")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if template_id in state["templates"]:
                raise LocalWorkbenchError("template_already_exists", 409)
            state["templates"][template_id] = template
            event = self._event(
                state,
                "template_registered",
                subject_type="template",
                subject_id=template_id,
                detail={"step_count": len(template["steps"])},
            )
            self._write(state)
        return {**deepcopy(template), "receipt": self._public_event(event)}

    def prepare_handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        handoff_id = _safe_id(payload.get("handoff_id"), "handoff_id")
        role = _text(payload.get("recipient_role") or "reviewer", "recipient_role", limit=64)
        if role not in _HANDOFF_ROLES:
            raise LocalWorkbenchError("handoff_role_invalid")
        handoff = {
            "handoff_id": handoff_id,
            "recipient_label": _text(payload.get("recipient_label"), "recipient_label", limit=128),
            "recipient_role": role,
            "scope_summary": _text(payload.get("scope_summary"), "scope_summary", limit=2_000),
            "status": "prepared_not_transmitted",
            "redaction_required": True,
            "delivery_requires_confirmation": True,
            "created_at": _now(),
        }
        if not handoff["recipient_label"] or not handoff["scope_summary"]:
            raise LocalWorkbenchError("handoff_recipient_and_scope_required")
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            if handoff_id in state["handoffs"]:
                raise LocalWorkbenchError("handoff_already_exists", 409)
            state["handoffs"][handoff_id] = handoff
            event = self._event(
                state,
                "handoff_prepared",
                subject_type="handoff",
                subject_id=handoff_id,
                detail={"recipient_role": role},
            )
            self._write(state)
        return {**deepcopy(handoff), "receipt": self._public_event(event)}

    def portable_manifest(self) -> dict[str, Any]:
        """Return a privacy-safe pre-export manifest, never an export itself."""

        state = self._read()
        summary = {
            "models": len(state["models"]),
            "plans": len(state["plans"]),
            "work_items": len(state["work_items"]),
            "sources": len(state["sources"]),
            "automations": len(state["automations"]),
            "extensions": len(state["extensions"]),
            "connectors": len(state["connectors"]),
            "templates": len(state["templates"]),
            "handoffs": len(state["handoffs"]),
            "evaluations": len(state["evaluations"]),
        }
        return {
            "schema_version": "local_workbench_portable_manifest_v1",
            "scope_id": self.scope_id,
            "state_revision": int(state.get("revision") or 0),
            "counts": summary,
            "event_chain_head": str((state.get("events") or [{}])[-1].get("event_hash") or ""),
            "contains_private_content": False,
            "contains_storage_paths": False,
            "export_not_created": True,
            "confirmation_required_before_export": bool(
                state["privacy"].get("portable_exports_require_confirmation", True)
            ),
            "review_required": True,
        }

    def record_release_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence_id = _safe_id(payload.get("evidence_id"), "evidence_id")
        control = _text(payload.get("control"), "release_control", limit=64)
        status = _text(payload.get("status"), "release_evidence_status", limit=64)
        sha256 = _text(payload.get("sha256"), "release_evidence_sha256", limit=128).casefold()
        if control not in _RELEASE_CONTROLS or status not in _RELEASE_EVIDENCE_STATUSES:
            raise LocalWorkbenchError("release_evidence_classification_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise LocalWorkbenchError("release_evidence_sha256_invalid")
        record = {
            "evidence_id": evidence_id,
            "control": control,
            "status": status,
            "sha256": sha256,
            "summary": _text(payload.get("summary"), "release_evidence_summary", limit=1_000),
            "recorded_at": _now(),
            "human_attestation": bool(payload.get("human_attestation", False)),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            state["release_evidence"][evidence_id] = record
            event = self._event(
                state,
                "release_evidence_recorded",
                subject_type="release_evidence",
                subject_id=evidence_id,
                detail={"control": control, "status": status},
            )
            self._write(state)
        return {**deepcopy(record), "receipt": self._public_event(event)}

    def release_readiness(self) -> dict[str, Any]:
        """Fail closed until every required control has real pass evidence."""

        state = self._read()
        records = list(state["release_evidence"].values())
        latest: dict[str, dict[str, Any]] = {}
        for record in sorted(records, key=lambda item: str(item.get("recorded_at") or "")):
            latest[str(record.get("control") or "")] = record
        controls: list[dict[str, Any]] = []
        blockers: list[str] = []
        human_controls = {"security", "privacy", "accessibility", "legal", "operations"}
        for control in sorted(_RELEASE_CONTROLS):
            record = latest.get(control)
            passed = bool(record and record.get("status") == "pass")
            attested = bool(record and record.get("human_attestation"))
            if control in human_controls:
                passed = passed and attested
            if not passed:
                blockers.append(f"release_control_not_passed:{control}")
            controls.append(
                {
                    "control": control,
                    "status": "pass"
                    if passed
                    else str(record.get("status") if record else "missing"),
                    "human_attestation_required": control in human_controls,
                    "human_attested": attested,
                }
            )
        if not state["artifact_admissions"]:
            blockers.append("no_verified_local_model_artifact")
        return {
            "schema_version": "local_workbench_release_readiness_v1",
            "status": "pass" if not blockers else "blocked",
            "controls": controls,
            "verified_artifact_count": len(state["artifact_admissions"]),
            "blockers": blockers,
            "automatic_ga_release_authorized": False,
            "notice": (
                "This gate records evidence and fails closed; it does not replace required "
                "human sign-offs."
            ),
            "review_required": True,
        }

    def record_evaluation(self, payload: dict[str, Any]) -> dict[str, Any]:
        evaluation_id = _safe_id(payload.get("evaluation_id"), "evaluation_id")
        metrics = payload.get("metrics")
        if not isinstance(metrics, dict) or len(metrics) > 50:
            raise LocalWorkbenchError("evaluation_metrics_invalid")
        normalized: dict[str, float] = {}
        for name, value in metrics.items():
            key = _safe_id(name, "metric_name")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise LocalWorkbenchError("evaluation_metric_invalid") from exc
            if not -1_000_000 <= number <= 1_000_000:
                raise LocalWorkbenchError("evaluation_metric_invalid")
            normalized[key] = number
        record = {
            "evaluation_id": evaluation_id,
            "subject_id": _safe_id(payload.get("subject_id"), "subject_id"),
            "kind": _text(payload.get("kind") or "workflow", "evaluation_kind", limit=128),
            "metrics": normalized,
            "sample_count": max(0, int(payload.get("sample_count") or 0)),
            "review_required": True,
            "recorded_at": _now(),
        }
        with exclusive_file_lock(self.lock_path):
            state = self._read()
            state["evaluations"][evaluation_id] = record
            event = self._event(
                state,
                "evaluation_recorded",
                subject_type="evaluation",
                subject_id=evaluation_id,
                detail={"subject_id": record["subject_id"], "metric_count": len(normalized)},
            )
            self._write(state)
        return {**deepcopy(record), "receipt": self._public_event(event)}
