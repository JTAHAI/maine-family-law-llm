"""Encrypted, device-scoped setup state for optional local AI.

This module intentionally does not download, install, admit, or start a model.
It gives the production UI one durable, truthful place to assess a computer and
remember the person's selected operating mode before a verified model catalog
is available.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
from .catalog import LocalAiCatalog


class LocalAiSetupError(ValueError):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def default_local_ai_state_root() -> Path:
    configured = str(os.environ.get("MFL_LOCAL_AI_STATE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    if os.name == "nt":
        return (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "local-ai").resolve()
    return (Path.home() / ".local" / "state" / "maine-family-law-llm" / "local-ai").resolve()


class LocalAiSetupStore:
    """Small encrypted state store, partitioned by a browser session digest."""

    schema = "maine_family_law_llm.local_ai_setup.v1"

    def __init__(self, *, root: str | Path | None = None, audience: str, encryption_key: str | None = None):
        clean_audience = str(audience or "").strip()
        if not clean_audience or len(clean_audience) > 256:
            raise LocalAiSetupError("local_ai_setup_audience_invalid", 403)
        self.root = Path(root or default_local_ai_state_root()).resolve(strict=False)
        self.audience = hashlib.sha256(clean_audience.encode("utf-8")).hexdigest()[:32]
        self.directory = self.root / "profiles" / self.audience
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.directory / "setup.json.enc"

    @property
    def lock_path(self) -> Path:
        return self.directory / ".setup.lock"

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "revision": 0,
            "mode": "basic",
            "events": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=512 * 1024, require_object=True)
            )
        except Exception as exc:
            raise LocalAiSetupError("local_ai_setup_unavailable") from exc
        if state.get("schema") != self.schema or not isinstance(state.get("events"), list):
            raise LocalAiSetupError("local_ai_setup_unavailable")
        if len(state["events"]) > 256:
            raise LocalAiSetupError("local_ai_setup_unavailable")
        previous = ""
        for event in state["events"]:
            copy = dict(event)
            event_hash = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != previous or event_hash != _digest(copy):
                raise LocalAiSetupError("local_ai_setup_history_invalid")
            previous = event_hash
        return state

    def _write(self, state: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _recommendation(profile: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
        available_memory = max(0, int(profile.get("available_memory_bytes") or 0))
        disk_free = max(0, int(profile.get("disk_free_bytes") or 0))
        blockers: list[str] = []
        if not available_memory:
            blockers.append("available_memory_unverified")
        elif available_memory < 4 * 1024**3:
            blockers.append("insufficient_available_memory")
        if not disk_free:
            blockers.append("available_disk_unverified")
        elif disk_free < 2 * 1024**3:
            blockers.append("insufficient_available_disk")
        assessments = [LocalAiCatalog.assess(item, profile) for item in catalog.get("profiles") or []]
        eligible = [item for item in assessments if item["status"] == "eligible_for_install_review"]
        # Prefer the smaller eligible reasoning profile for the first install.
        # The catalog carries measured requirements; name/order never overrides
        # the runtime-specific assessment.
        preferred = min(
            eligible,
            key=lambda item: (
                item["selected_resource_profile"]["estimated_peak_memory_bytes"],
                item["selected_resource_profile"]["required_disk_bytes"],
            ),
        ) if eligible else None
        return {
            "schema_version": "local_ai_recommendation_v1",
            "status": "model_install_review_available" if preferred else ("basic_mode_recommended" if not blockers else "review_required"),
            "recommended_mode": "optional_model" if preferred else "basic",
            "recommended_profile_id": preferred["profile_id"] if preferred else None,
            "installable_model_count": int(catalog.get("profile_count") or 0),
            "installable_models": list(catalog.get("profiles") or []),
            "model_assessments": assessments,
            "blockers": blockers,
            "explanation": (
                "A verified local reasoning model can be reviewed for this PC before installation."
                if preferred else
                "Local source-backed answers, OCR, record review, and forms are available now. "
                "A downloadable model will appear here only after its files, license, integrity record, and device requirements are verified."
            ),
            "basis": "local_hardware_snapshot",
            "review_required": True,
            "network_used": False,
        }

    @staticmethod
    def _conversation_setup(profile: dict[str, Any]) -> dict[str, Any]:
        """Translate device headroom into plain choices for the chat UI.

        This is deliberately an advisory preflight, not a model probe,
        download, admission, or promise that a local runtime is installed.
        """
        gib = 1024**3
        memory = max(0, int(profile.get("available_memory_bytes") or 0))
        vram = max(0, int(profile.get("available_vram_bytes") or 0))
        standard = memory >= 6 * gib or (vram >= 4 * gib and memory >= 2 * gib)
        capable = memory >= 10 * gib or (vram >= int(5.5 * gib) and memory >= 2 * gib)
        choices = [
            {
                "id": "qwen3:4b",
                "label": "Standard local AI",
                "plain_description": "A smaller option for everyday, source-bound help.",
                "eligible": standard,
            },
            {
                "id": "qwen3:8b",
                "label": "More capable local AI",
                "plain_description": "A larger option that needs more room on this PC.",
                "eligible": capable,
            },
        ]
        if capable:
            message = "This PC appears able to try either local AI option. Start with Standard if you want the lighter choice."
        elif standard:
            message = "This PC appears able to use Standard local AI. The larger option is not recommended right now."
        else:
            message = "This PC is not showing enough free room for optional local AI right now. The regular source-backed chat still works."
        return {
            "schema_version": "local_ai_conversation_setup_v1",
            "status": "options_available" if standard else "basic_chat_recommended",
            "message": message,
            "choices": choices,
            "model_presence_checked": False,
            "download_available_in_app": True,
            "technical_details_available": True,
            "review_required": True,
            "network_used": False,
        }

    def status(self) -> dict[str, Any]:
        state = self._load()
        profile = profile_hardware(self.root).as_dict()
        catalog = LocalAiCatalog().status()
        return {
            "schema_version": "local_ai_setup_status_v1",
            "mode": state.get("mode", "basic"),
            "revision": int(state.get("revision") or 0),
            "recommendation": self._recommendation(profile, catalog),
            "catalog": catalog,
            "hardware": profile,
            "conversation_setup": self._conversation_setup(profile),
            "state_encrypted": True,
            "matter_content_stored": False,
            "review_required": True,
            "network_used": False,
        }

    def assess_profile(self, profile_id: str) -> dict[str, Any]:
        """Assess one catalog profile without initiating an install or model run."""
        hardware = profile_hardware(self.root).as_dict()
        profile = LocalAiCatalog().profile(profile_id)
        return {
            "schema_version": "local_ai_setup_profile_assessment_v1",
            "assessment": LocalAiCatalog.assess(profile, hardware),
            "hardware": hardware,
            "state_encrypted": True,
            "matter_content_stored": False,
            "review_required": True,
            "network_used": False,
        }

    def choose_basic_mode(
        self,
        *,
        expected_revision: int,
        user_confirmed: bool,
        audit_event_id: str = "",
    ) -> dict[str, Any]:
        if user_confirmed is not True:
            raise LocalAiSetupError("local_ai_setup_confirmation_required")
        self.directory.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            if int(state.get("revision") or 0) != int(expected_revision):
                raise LocalAiSetupError("local_ai_setup_revision_conflict")
            event = {
                "event_id": "local_ai_" + hashlib.sha256((self.audience + _now()).encode()).hexdigest()[:24],
                "at": _now(),
                "action": "basic_mode_selected",
                "mode": "basic",
                "review_required": True,
                "audit_event_id": str(audit_event_id or "")[:128],
                "previous_event_hash": str(state["events"][-1].get("event_hash") or "") if state["events"] else "",
            }
            event["event_hash"] = _digest(event)
            state["mode"] = "basic"
            state["events"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._write(state)
        return {"status": "basic_mode_selected", "revision": state["revision"], "receipt": event, "review_required": True, "network_used": False}
