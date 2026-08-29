"""Optional local user-presence protection for an encrypted matter.

This module never captures, stores, or infers biometric data.  When the
Windows Hello runtime is available, Windows performs the user-presence prompt;
the app receives only a verified/not-verified result.  Policy records are
encrypted with the local vault material and session grants are process-local,
short lived, non-exportable, and scoped to one tenant/matter pair.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file
from .local_encryption import LocalEnvelopeEncryptor


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?")
_MAX_POLICY_BYTES = 512 * 1024
_DEFAULT_SESSION_SECONDS = 15 * 60
_MAX_SESSION_SECONDS = 60 * 60
_POLICY_SCHEMA = "matter_unlock_policy_v1"
_FALLBACKS = {"local_vault_recovery", "admin_recovery_required"}
_SESSION_LOCK = threading.RLock()
_UNLOCK_SESSIONS: dict[str, float] = {}


class MatterUnlockError(ValueError):
    """A safe, non-secret unlock-policy error."""


class UserPresenceProvider(Protocol):
    def availability(self) -> dict[str, str]: ...

    def verify(self, reason: str) -> dict[str, str]: ...


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identifier(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise MatterUnlockError(f"invalid_{field}")
    return normalized


class WindowsHelloPresenceProvider:
    """Best-effort wrapper around the optional Windows Runtime binding.

    The dependency is intentionally optional: a package missing the WinRT
    projection never downgrades to a password prompt or an app-managed
    biometric flow.  It simply reports that Hello is unavailable and leaves
    the encrypted-matter fallback policy visible for review.
    """

    @staticmethod
    def _run(awaitable: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)
        raise MatterUnlockError("windows_hello_event_loop_unavailable")

    @staticmethod
    def _api() -> Any:
        if os.name != "nt":
            raise MatterUnlockError("windows_hello_windows_only")
        try:
            from winrt.windows.security.credentials.ui import UserConsentVerifier  # type: ignore[import-not-found]
        except Exception as exc:
            raise MatterUnlockError("windows_hello_runtime_unavailable") from exc
        return UserConsentVerifier

    def availability(self) -> dict[str, str]:
        try:
            verifier = self._api()
            result = self._run(verifier.check_availability_async())
            value = str(result).casefold()
            if "available" == value.split(".")[-1]:
                return {"status": "available", "provider": "windows_hello"}
            return {"status": "unavailable", "provider": "windows_hello", "reason": "windows_hello_not_available"}
        except MatterUnlockError as exc:
            return {"status": "unavailable", "provider": "windows_hello", "reason": str(exc)}

    def verify(self, reason: str) -> dict[str, str]:
        availability = self.availability()
        if availability["status"] != "available":
            return availability
        try:
            verifier = self._api()
            result = self._run(verifier.request_verification_async(reason))
            if str(result).casefold().split(".")[-1] == "verified":
                return {"status": "verified", "provider": "windows_hello"}
            return {"status": "blocked", "provider": "windows_hello", "reason": "windows_hello_not_verified"}
        except MatterUnlockError as exc:
            return {"status": "blocked", "provider": "windows_hello", "reason": str(exc)}


class MatterUnlockBroker:
    """Encrypted policy and ephemeral user-presence grants for one store root."""

    def __init__(
        self,
        root: str | Path,
        *,
        root_secret: str | bytes,
        presence_provider: UserPresenceProvider | None = None,
    ) -> None:
        self.root = Path(root).resolve() / ".mfl-matter-unlock"
        secret = root_secret if isinstance(root_secret, bytes) else str(root_secret).encode("utf-8")
        self._encryptor = LocalEnvelopeEncryptor(base64.urlsafe_b64encode(secret).decode("ascii"))
        self._presence = presence_provider or WindowsHelloPresenceProvider()

    def _policy_path(self, tenant_id: str, matter_id: str) -> Path:
        tenant = _identifier(tenant_id, "tenant_id")
        matter = _identifier(matter_id, "matter_id")
        path = (self.root / tenant / f"{matter}.json.enc").resolve()
        if self.root not in path.parents:
            raise MatterUnlockError("unlock_policy_path_invalid")
        return path

    def _session_key(self, tenant_id: str, matter_id: str) -> str:
        return hashlib.sha256(f"{self.root}|{tenant_id}|{matter_id}".encode("utf-8")).hexdigest()

    @staticmethod
    def _event(state: dict[str, Any], event_type: str) -> None:
        events = list(state.get("events") or [])
        previous_hash = str(events[-1].get("event_hash") or "0" * 64) if events else "0" * 64
        event = {"event_type": event_type, "timestamp": _now(), "previous_hash": previous_hash}
        event["event_hash"] = _digest(event)
        state["events"] = [*events[-127:], event]

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> dict[str, Any]:
        head = "0" * 64
        blockers: list[str] = []
        events = list(state.get("events") or [])
        for index, event in enumerate(events):
            candidate = dict(event)
            event_hash = str(candidate.pop("event_hash", ""))
            if candidate.get("previous_hash") != head:
                blockers.append(f"unlock_audit_previous_hash_mismatch:{index}")
            if not hmac.compare_digest(_digest(candidate), event_hash):
                blockers.append(f"unlock_audit_hash_mismatch:{index}")
            head = event_hash
        return {"verified": not blockers, "event_count": len(events), "blockers": blockers}

    def _default(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        return {
            "schema_version": _POLICY_SCHEMA,
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "enabled": False,
            "fallback_policy": "local_vault_recovery",
            "created_at": _now(),
            "updated_at": _now(),
            "events": [],
        }

    def _load(self, path: Path, tenant_id: str, matter_id: str) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            envelope = json.loads(read_bounded_regular_file(path, max_bytes=_MAX_POLICY_BYTES).decode("utf-8"))
            state = self._encryptor.decrypt_json(envelope)
        except Exception as exc:
            raise MatterUnlockError("matter_unlock_policy_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != _POLICY_SCHEMA:
            raise MatterUnlockError("matter_unlock_policy_invalid")
        if state.get("tenant_id") != tenant_id or state.get("matter_id") != matter_id:
            raise MatterUnlockError("matter_unlock_scope_mismatch")
        return state

    def _write(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, _canonical(self._encryptor.encrypt_json(state)), mode=0o600)

    def _mutate(self, tenant_id: str, matter_id: str, callback) -> Any:
        path = self._policy_path(tenant_id, matter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(path.with_suffix(".lock")):
            state = self._load(path, tenant_id, matter_id) or self._default(tenant_id, matter_id)
            result, changed = callback(state)
            if changed:
                state["updated_at"] = _now()
                self._write(path, state)
            return result

    def _public(self, state: dict[str, Any]) -> dict[str, Any]:
        tenant = str(state.get("tenant_id") or "")
        matter = str(state.get("matter_id") or "")
        expires_at = 0.0
        with _SESSION_LOCK:
            expires_at = _UNLOCK_SESSIONS.get(self._session_key(tenant, matter), 0.0)
            if expires_at <= time.monotonic():
                _UNLOCK_SESSIONS.pop(self._session_key(tenant, matter), None)
                expires_at = 0.0
        return {
            "status": "enabled" if state.get("enabled") else "not_enabled",
            "tenant_id": tenant,
            "matter_id": matter,
            "enabled": bool(state.get("enabled")),
            "provider": "windows_hello",
            "provider_availability": self._presence.availability(),
            "fallback_policy": str(state.get("fallback_policy") or "local_vault_recovery"),
            "unlocked_for_session": expires_at > 0,
            "session_grant_persisted": False,
            "biometric_data_collected": False,
            "review_required": True,
            "audit": self._verify_events(state),
        }

    def status(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _identifier(tenant_id, "tenant_id")
        matter = _identifier(matter_id, "matter_id")
        state = self._load(self._policy_path(tenant, matter), tenant, matter)
        return self._public(state or self._default(tenant, matter))

    def configure(self, tenant_id: str, matter_id: str, *, enabled: bool, fallback_policy: str, approved: bool) -> dict[str, Any]:
        tenant = _identifier(tenant_id, "tenant_id")
        matter = _identifier(matter_id, "matter_id")
        if not approved:
            raise MatterUnlockError("matter_unlock_approval_required")
        if fallback_policy not in _FALLBACKS:
            raise MatterUnlockError("matter_unlock_fallback_invalid")
        availability = self._presence.availability()
        if enabled and availability.get("status") != "available":
            raise MatterUnlockError("windows_hello_unavailable")

        def update(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
            state["enabled"] = bool(enabled)
            state["fallback_policy"] = fallback_policy
            self._event(state, "matter_unlock_enabled" if enabled else "matter_unlock_disabled")
            if not enabled:
                with _SESSION_LOCK:
                    _UNLOCK_SESSIONS.pop(self._session_key(tenant, matter), None)
            return self._public(state), True

        return self._mutate(tenant, matter, update)

    def verify(self, tenant_id: str, matter_id: str, *, approved: bool, session_seconds: int = _DEFAULT_SESSION_SECONDS) -> dict[str, Any]:
        tenant = _identifier(tenant_id, "tenant_id")
        matter = _identifier(matter_id, "matter_id")
        if not approved:
            raise MatterUnlockError("matter_unlock_approval_required")

        def verify(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
            if not state.get("enabled"):
                raise MatterUnlockError("matter_unlock_not_enabled")
            result = self._presence.verify("Unlock the active Maine Family Law LLM matter")
            if result.get("status") != "verified":
                raise MatterUnlockError(str(result.get("reason") or "windows_hello_not_verified"))
            bounded_seconds = max(60, min(int(session_seconds), _MAX_SESSION_SECONDS))
            with _SESSION_LOCK:
                _UNLOCK_SESSIONS[self._session_key(tenant, matter)] = time.monotonic() + bounded_seconds
            self._event(state, "matter_unlock_verified")
            report = self._public(state)
            report["status"] = "unlocked"
            return report, True

        return self._mutate(tenant, matter, verify)

    def lock(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _identifier(tenant_id, "tenant_id")
        matter = _identifier(matter_id, "matter_id")
        with _SESSION_LOCK:
            _UNLOCK_SESSIONS.pop(self._session_key(tenant, matter), None)
        return {**self.status(tenant, matter), "status": "locked", "review_required": True}

    def assert_unlocked(self, tenant_id: str, matter_id: str) -> None:
        status = self.status(tenant_id, matter_id)
        if status["enabled"] and not status["unlocked_for_session"]:
            raise MatterUnlockError("matter_unlock_required")


__all__ = ["MatterUnlockBroker", "MatterUnlockError", "UserPresenceProvider", "WindowsHelloPresenceProvider"]
