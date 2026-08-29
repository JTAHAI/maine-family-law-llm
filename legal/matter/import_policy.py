"""Encrypted matter import policies that can only tighten the global safety floor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,119}\Z")
_MAX_BYTES = 250 * 1024 * 1024
_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".jsonl", ".yaml", ".yml", ".html", ".htm", ".rtf", ".eml", ".xlsx", ".pptx", ".zip", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".wav", ".mp3", ".mp4", ".mov"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
_MAX_STATE_BYTES = 2 * 1024 * 1024


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _profile_id(value: Any) -> str:
    candidate = str(value or "").strip()
    if not _ID.fullmatch(candidate):
        raise IntakeWorkbenchError("import_policy_profile_id_invalid", 422)
    return candidate


def _floor() -> dict[str, Any]:
    return {"max_file_bytes": _MAX_BYTES, "allowed_extensions": sorted(_EXTENSIONS), "privacy_scan_required": True, "quarantine_unknown_extensions": True, "local_ocr_review_for_images": True, "symlinks_blocked": True}


def _validate(payload: dict[str, Any]) -> dict[str, Any]:
    requested_bytes = int(payload.get("max_file_bytes") or _MAX_BYTES)
    if requested_bytes < 1 or requested_bytes > _MAX_BYTES:
        raise IntakeWorkbenchError("import_policy_max_file_bytes_weakens_global_floor", 422)
    extensions = payload.get("allowed_extensions") or sorted(_EXTENSIONS)
    if not isinstance(extensions, list):
        raise IntakeWorkbenchError("import_policy_allowed_extensions_invalid", 422)
    allowed = sorted({str(item).strip().lower() for item in extensions if str(item).strip()})
    if not allowed or any(item not in _EXTENSIONS for item in allowed):
        raise IntakeWorkbenchError("import_policy_allowed_extensions_weakens_global_floor", 422)
    for name in ("privacy_scan_required", "quarantine_unknown_extensions", "local_ocr_review_for_images"):
        if payload.get(name, True) is not True:
            raise IntakeWorkbenchError(f"import_policy_{name}_weakens_global_floor", 422)
    return {"max_file_bytes": requested_bytes, "allowed_extensions": allowed, "privacy_scan_required": True, "quarantine_unknown_extensions": True, "local_ocr_review_for_images": True, "symlinks_blocked": True}


class ImportPolicyStore:
    schema = "maine_family_law_llm.import_policy.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        self.root = self.case_root / "18_SETTINGS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("import_policy_store_unavailable", 409)
        self.root.mkdir(parents=True, exist_ok=True)
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or LocalEnvelopeEncryptor.development_default)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "import-policy.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".import-policy.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "profiles": {}, "active_profile_id": "", "history": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("import_policy_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("import_policy_cross_matter_access_denied", 404)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = _profile_id(payload.get("profile_id"))
        policy = _validate(payload)
        with exclusive_file_lock(self.lock):
            state = self._load()
            if profile_id in (state.get("profiles") or {}):
                raise IntakeWorkbenchError("import_policy_profile_id_exists", 409)
            previous_hash = str((state.get("history") or [{}])[-1].get("event_hash") or "")
            event = {"event_id": f"import_policy_{uuid.uuid4().hex}", "at": _now(), "action": "profile_created_and_activated", "profile_id": profile_id, "policy_hash": _hash(policy), "previous_event_hash": previous_hash, "review_required": True}
            event["event_hash"] = _hash(event)
            profile = {"profile_id": profile_id, "created_at": event["at"], "policy": policy, "audit_event_id": event["event_id"], "review_required": True, "notice": "This profile only tightens the global import safeguards. It is enforced before canonical corpus parsing and file staging; blocked candidates are quarantined for review."}
            state.setdefault("profiles", {})[profile_id] = profile
            state["active_profile_id"] = profile_id
            state.setdefault("history", []).append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {"status": "pass", "profile": profile, "review_required": True}

    def inventory(self) -> dict[str, Any]:
        state = self._load()
        profiles = [dict(item) for _, item in sorted(dict(state.get("profiles") or {}).items())]
        return {"status": "pass", "active_profile_id": str(state.get("active_profile_id") or ""), "profiles": profiles, "global_floor": _floor(), "review_required": True}

    def active_policy(self) -> dict[str, Any]:
        state = self._load()
        profile_id = str(state.get("active_profile_id") or "")
        profile = dict((state.get("profiles") or {}).get(profile_id) or {})
        return dict(profile.get("policy") or _floor())

    @staticmethod
    def evaluate_path(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
        suffix = path.suffix.lower()
        if path.is_symlink():
            return {"status": "quarantine", "reason": "symlink_blocked", "review_required": True}
        try:
            size = path.stat().st_size
        except OSError:
            return {"status": "quarantine", "reason": "candidate_unavailable", "review_required": True}
        if size > int(policy["max_file_bytes"]):
            return {"status": "quarantine", "reason": "profile_size_limit_exceeded", "review_required": True}
        if suffix not in set(policy["allowed_extensions"]):
            return {"status": "quarantine", "reason": "profile_extension_not_allowed", "review_required": True}
        return {"status": "accept", "reason": "accepted_with_privacy_and_quarantine_floor", "ocr_review_required": suffix in _IMAGE_EXTENSIONS and bool(policy["local_ocr_review_for_images"]), "review_required": True}


def active_import_policy(case_root: str | Path) -> dict[str, Any]:
    root = Path(case_root).expanduser().resolve()
    path = root / "18_SETTINGS" / "import-policy.json.enc"
    if not path.exists():
        return _floor()
    return ImportPolicyStore(root).active_policy()
