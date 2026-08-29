"""Per-matter data-key hierarchy for new external matter-store envelopes.

The hierarchy is intentionally separate from the legacy local envelope reader.
It gives each tenant/matter pair an independently wrapped AES-256 data key,
keeps retired keys only for decrypting older envelopes, and fails closed after
revocation or cryptographic deletion.  The root wrapping key is derived from
the DPAPI-protected local vault secret; it is never serialized in the matter
store, API response, audit event, or recovery record.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file
from .local_encryption import default_matter_passphrase


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?")
_PURPOSE_RE = re.compile(r"[a-z][a-z0-9_-]{1,62}")
_MAX_STATE_BYTES = 2 * 1024 * 1024
_ROOT_KDF_SALT = b"maine-family-law-llm-matter-key-hierarchy-v1"
_RECOVERY_ITERATIONS = 300_000
# The schema version, not a custom cipher label, distinguishes this envelope
# from the legacy passphrase-derived AES-GCM envelope.
_ALGORITHM = "aes-256-gcm"
_SCHEMA_VERSION = "matter_key_hierarchy_v1"


class MatterKeyHierarchyError(ValueError):
    """Raised for a safe, non-secret hierarchy state or authorization failure."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: object, *, field: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(str(value).encode("ascii"))
    except Exception as exc:  # pragma: no cover - defensive input boundary
        raise MatterKeyHierarchyError(f"invalid_{field}") from exc
    if not decoded:
        raise MatterKeyHierarchyError(f"invalid_{field}")
    return decoded


def _validate_identifier(value: str, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise MatterKeyHierarchyError(f"invalid_{field}")
    return normalized


def _validate_purpose(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _PURPOSE_RE.fullmatch(normalized):
        raise MatterKeyHierarchyError("invalid_purpose")
    return normalized


class MatterKeyHierarchy:
    """Manage independently wrapped matter data keys with no secret-bearing API."""

    def __init__(self, root: str | Path, *, root_secret: str | bytes | None = None) -> None:
        self.root = Path(root).resolve() / ".mfl-key-hierarchy"
        # Construction is read-only.  Creating a hierarchy directory merely by
        # opening a matter would leave misleading empty state beside legacy or
        # direct-open matters; mutation creates the scoped directory instead.
        material = root_secret if root_secret is not None else default_matter_passphrase()
        material_bytes = material if isinstance(material, bytes) else str(material).encode("utf-8")
        if len(material_bytes) < 12:
            raise MatterKeyHierarchyError("root_secret_too_short")
        self._root_key = hashlib.pbkdf2_hmac(
            "sha256", material_bytes, _ROOT_KDF_SALT, 300_000, dklen=32
        )

    def _state_path(self, tenant_id: str, matter_id: str) -> Path:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")
        path = (self.root / tenant / f"{matter}.json").resolve()
        if self.root not in path.parents:
            raise MatterKeyHierarchyError("key_state_path_invalid")
        return path

    @staticmethod
    def _aad(tenant_id: str, matter_id: str, purpose: str, key_id: str, *, kind: str) -> bytes:
        return f"{_SCHEMA_VERSION}|{kind}|{tenant_id}|{matter_id}|{purpose}|{key_id}".encode("utf-8")

    def _wrap_root(self, key: bytes, tenant_id: str, matter_id: str, key_id: str) -> dict[str, str]:
        nonce = os.urandom(12)
        cipher = AESGCM(self._root_key).encrypt(
            nonce,
            key,
            self._aad(tenant_id, matter_id, "matter_key", key_id, kind="root_wrap"),
        )
        return {"nonce": _encode(nonce), "ciphertext": _encode(cipher)}

    def _unwrap_root(self, wrapped: dict[str, Any], tenant_id: str, matter_id: str, key_id: str) -> bytes:
        nonce = _decode(wrapped.get("nonce"), field="root_wrap_nonce")
        cipher = _decode(wrapped.get("ciphertext"), field="root_wrap_ciphertext")
        if len(nonce) != 12:
            raise MatterKeyHierarchyError("invalid_root_wrap_nonce")
        try:
            key = AESGCM(self._root_key).decrypt(
                nonce,
                cipher,
                self._aad(tenant_id, matter_id, "matter_key", key_id, kind="root_wrap"),
            )
        except Exception as exc:
            raise MatterKeyHierarchyError("root_wrap_integrity_failed") from exc
        if len(key) != 32:
            raise MatterKeyHierarchyError("invalid_matter_key")
        return key

    @staticmethod
    def _event(state: dict[str, Any], event_type: str, *, key_id: str | None = None) -> None:
        events = list(state.get("events") or [])
        previous_hash = str(events[-1].get("event_hash") or "0" * 64) if events else "0" * 64
        event = {
            "event_id": f"mkh-{secrets.token_hex(10)}",
            "event_type": event_type,
            "timestamp": _now(),
            "key_id": key_id,
            "previous_hash": previous_hash,
        }
        event["event_hash"] = _fingerprint(_canonical(event))
        events.append(event)
        state["events"] = events[-256:]

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> dict[str, Any]:
        head = "0" * 64
        blockers: list[str] = []
        events = list(state.get("events") or [])
        for index, event in enumerate(events):
            candidate = dict(event)
            event_hash = str(candidate.pop("event_hash", ""))
            if candidate.get("previous_hash") != head:
                blockers.append(f"event_previous_hash_mismatch:{index}")
            if not hmac.compare_digest(_fingerprint(_canonical(candidate)), event_hash):
                blockers.append(f"event_hash_mismatch:{index}")
            head = event_hash
        return {"verified": not blockers, "event_count": len(events), "chain_head": head, "blockers": blockers}

    def _new_state(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        key_id = f"mkh-{secrets.token_hex(16)}"
        key = secrets.token_bytes(32)
        state: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "status": "active",
            "active_key_id": key_id,
            "created_at": _now(),
            "keys": [
                {
                    "key_id": key_id,
                    "status": "active",
                    "created_at": _now(),
                    "wrapped_key": self._wrap_root(key, tenant_id, matter_id, key_id),
                }
            ],
            "recovery": {"enabled": False},
            "events": [],
        }
        self._event(state, "matter_key_initialized", key_id=key_id)
        return state

    def _load(self, path: Path, tenant_id: str, matter_id: str) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(read_bounded_regular_file(path, max_bytes=_MAX_STATE_BYTES).decode("utf-8"))
        except Exception as exc:
            raise MatterKeyHierarchyError("key_state_unavailable") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            raise MatterKeyHierarchyError("key_state_invalid")
        if payload.get("tenant_id") != tenant_id or payload.get("matter_id") != matter_id:
            raise MatterKeyHierarchyError("key_state_scope_mismatch")
        if not isinstance(payload.get("keys"), list):
            raise MatterKeyHierarchyError("key_state_invalid")
        return payload

    @staticmethod
    def _write(path: Path, state: dict[str, Any]) -> None:
        atomic_write_bytes(path, _canonical(state), mode=0o600)

    def _mutate(
        self, tenant_id: str, matter_id: str, callback, *, create_if_missing: bool = True
    ) -> Any:
        path = self._state_path(tenant_id, matter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(".lock")
        with exclusive_file_lock(lock_path):
            state = self._load(path, tenant_id, matter_id)
            created = False
            if state is None and create_if_missing:
                state = self._new_state(tenant_id, matter_id)
                created = True
            result, changed = callback(state)
            if changed or created:
                self._write(path, state)
            return result

    @staticmethod
    def _key_record(state: dict[str, Any], key_id: str) -> dict[str, Any]:
        for row in state.get("keys") or []:
            if isinstance(row, dict) and hmac.compare_digest(str(row.get("key_id") or ""), key_id):
                return row
        raise MatterKeyHierarchyError("key_id_unavailable")

    def _active_key(self, state: dict[str, Any], tenant_id: str, matter_id: str) -> tuple[str, bytes]:
        if state.get("status") != "active":
            raise MatterKeyHierarchyError(f"matter_key_{state.get('status') or 'unavailable'}")
        key_id = str(state.get("active_key_id") or "")
        record = self._key_record(state, key_id)
        if record.get("status") != "active" or not isinstance(record.get("wrapped_key"), dict):
            raise MatterKeyHierarchyError("active_key_unavailable")
        return key_id, self._unwrap_root(record["wrapped_key"], tenant_id, matter_id, key_id)

    @staticmethod
    def _recovery_key(secret: str, salt: bytes) -> bytes:
        if len(secret) < 12:
            raise MatterKeyHierarchyError("recovery_secret_too_short")
        return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, _RECOVERY_ITERATIONS, dklen=32)

    def _wrap_recovery(self, key: bytes, secret: str, salt: bytes, tenant_id: str, matter_id: str, key_id: str) -> dict[str, str]:
        nonce = os.urandom(12)
        cipher = AESGCM(self._recovery_key(secret, salt)).encrypt(
            nonce,
            key,
            self._aad(tenant_id, matter_id, "matter_key", key_id, kind="recovery_wrap"),
        )
        return {"nonce": _encode(nonce), "ciphertext": _encode(cipher)}

    def _unwrap_recovery(self, wrapped: dict[str, Any], secret: str, salt: bytes, tenant_id: str, matter_id: str, key_id: str) -> bytes:
        nonce = _decode(wrapped.get("nonce"), field="recovery_wrap_nonce")
        cipher = _decode(wrapped.get("ciphertext"), field="recovery_wrap_ciphertext")
        if len(nonce) != 12:
            raise MatterKeyHierarchyError("invalid_recovery_wrap_nonce")
        try:
            key = AESGCM(self._recovery_key(secret, salt)).decrypt(
                nonce,
                cipher,
                self._aad(tenant_id, matter_id, "matter_key", key_id, kind="recovery_wrap"),
            )
        except Exception as exc:
            raise MatterKeyHierarchyError("recovery_secret_invalid") from exc
        if len(key) != 32:
            raise MatterKeyHierarchyError("invalid_matter_key")
        return key

    def ensure(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")

        def create(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None:
                state = self._new_state(tenant, matter)
                return self._public_status(state), True
            return self._public_status(state), False

        return self._mutate(tenant, matter, create)

    def status(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")
        state = self._load(self._state_path(tenant, matter), tenant, matter)
        if state is None:
            return {
                "status": "not_provisioned",
                "tenant_id": tenant,
                "matter_id": matter,
                "review_required": True,
                "recovery_enabled": False,
                "audit": {"verified": True, "event_count": 0, "chain_head": "0" * 64, "blockers": []},
            }
        return self._public_status(state)

    def _public_status(self, state: dict[str, Any]) -> dict[str, Any]:
        audit = self._verify_events(state)
        keys = [
            {
                "key_id": str(row.get("key_id") or ""),
                "status": str(row.get("status") or "unknown"),
                "created_at": str(row.get("created_at") or ""),
            }
            for row in state.get("keys") or []
            if isinstance(row, dict)
        ]
        return {
            "status": str(state.get("status") or "unknown"),
            "tenant_id": str(state.get("tenant_id") or ""),
            "matter_id": str(state.get("matter_id") or ""),
            "active_key_id": str(state.get("active_key_id") or "") if state.get("status") == "active" else None,
            "key_count": len(keys),
            "keys": keys,
            "recovery_enabled": bool((state.get("recovery") or {}).get("enabled")),
            "audit": audit,
            "review_required": True,
            "key_material_exported": False,
        }

    def encrypt_json(self, tenant_id: str, matter_id: str, purpose: str, payload: dict[str, Any]) -> dict[str, str]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")
        normalized_purpose = _validate_purpose(purpose)
        if not isinstance(payload, dict):
            raise MatterKeyHierarchyError("payload_object_required")

        def encrypt(state: dict[str, Any] | None) -> tuple[dict[str, str], bool]:
            if state is None:
                state = self._new_state(tenant, matter)
            key_id, key = self._active_key(state, tenant, matter)
            nonce = os.urandom(12)
            ciphertext = AESGCM(key).encrypt(
                nonce,
                _canonical(payload),
                self._aad(tenant, matter, normalized_purpose, key_id, kind="payload"),
            )
            return {
                "schema_version": _SCHEMA_VERSION,
                "algorithm": _ALGORITHM,
                "key_id": key_id,
                "purpose": normalized_purpose,
                "nonce": _encode(nonce),
                "ciphertext": _encode(ciphertext),
            }, True

        return self._mutate(tenant, matter, encrypt)

    def decrypt_json(self, tenant_id: str, matter_id: str, purpose: str, envelope: dict[str, Any]) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")
        normalized_purpose = _validate_purpose(purpose)
        if not isinstance(envelope, dict) or envelope.get("algorithm") != _ALGORITHM:
            raise MatterKeyHierarchyError("unsupported_matter_key_envelope")
        if envelope.get("purpose") != normalized_purpose:
            raise MatterKeyHierarchyError("envelope_purpose_mismatch")
        key_id = str(envelope.get("key_id") or "")
        state = self._load(self._state_path(tenant, matter), tenant, matter)
        if state is None or state.get("status") != "active":
            raise MatterKeyHierarchyError("matter_key_unavailable")
        record = self._key_record(state, key_id)
        if record.get("status") not in {"active", "retired"} or not isinstance(record.get("wrapped_key"), dict):
            raise MatterKeyHierarchyError("key_revoked_or_destroyed")
        key = self._unwrap_root(record["wrapped_key"], tenant, matter, key_id)
        nonce = _decode(envelope.get("nonce"), field="payload_nonce")
        ciphertext = _decode(envelope.get("ciphertext"), field="payload_ciphertext")
        if len(nonce) != 12:
            raise MatterKeyHierarchyError("invalid_payload_nonce")
        try:
            plaintext = AESGCM(key).decrypt(
                nonce,
                ciphertext,
                self._aad(tenant, matter, normalized_purpose, key_id, kind="payload"),
            )
            decoded = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise MatterKeyHierarchyError("matter_envelope_integrity_failed") from exc
        if not isinstance(decoded, dict):
            raise MatterKeyHierarchyError("matter_payload_invalid")
        return decoded

    def enroll_recovery(self, tenant_id: str, matter_id: str, recovery_secret: str) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")

        def enroll(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None:
                state = self._new_state(tenant, matter)
            if state.get("status") != "active":
                raise MatterKeyHierarchyError("matter_key_unavailable")
            salt = os.urandom(16)
            wrappers: dict[str, dict[str, str]] = {}
            for row in state.get("keys") or []:
                if not isinstance(row, dict) or row.get("status") not in {"active", "retired"}:
                    continue
                key_id = str(row.get("key_id") or "")
                key = self._unwrap_root(dict(row.get("wrapped_key") or {}), tenant, matter, key_id)
                wrappers[key_id] = self._wrap_recovery(key, recovery_secret, salt, tenant, matter, key_id)
            state["recovery"] = {
                "enabled": True,
                "kdf": f"pbkdf2_hmac_sha256_{_RECOVERY_ITERATIONS}",
                "salt": _encode(salt),
                "wrapped_keys": wrappers,
            }
            self._event(state, "matter_key_recovery_enrolled", key_id=str(state.get("active_key_id") or ""))
            return self._public_status(state), True

        return self._mutate(tenant, matter, enroll)

    def rotate(self, tenant_id: str, matter_id: str, *, recovery_secret: str | None = None) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")

        def rotate(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None:
                state = self._new_state(tenant, matter)
            if state.get("status") != "active":
                raise MatterKeyHierarchyError("matter_key_unavailable")
            recovery = dict(state.get("recovery") or {})
            salt = b""
            if recovery.get("enabled"):
                if not recovery_secret:
                    raise MatterKeyHierarchyError("recovery_rewrap_required")
                salt = _decode(recovery.get("salt"), field="recovery_salt")
                active = self._key_record(state, str(state.get("active_key_id") or ""))
                self._unwrap_recovery(
                    dict((recovery.get("wrapped_keys") or {}).get(active.get("key_id")) or {}),
                    recovery_secret,
                    salt,
                    tenant,
                    matter,
                    str(active.get("key_id") or ""),
                )
            previous_key_id = str(state.get("active_key_id") or "")
            previous = self._key_record(state, previous_key_id)
            previous["status"] = "retired"
            key_id = f"mkh-{secrets.token_hex(16)}"
            key = secrets.token_bytes(32)
            record = {
                "key_id": key_id,
                "status": "active",
                "created_at": _now(),
                "wrapped_key": self._wrap_root(key, tenant, matter, key_id),
            }
            state.setdefault("keys", []).append(record)
            state["active_key_id"] = key_id
            if recovery.get("enabled"):
                recovery.setdefault("wrapped_keys", {})[key_id] = self._wrap_recovery(
                    key, str(recovery_secret), salt, tenant, matter, key_id
                )
                state["recovery"] = recovery
            self._event(state, "matter_key_rotated", key_id=key_id)
            return self._public_status(state), True

        return self._mutate(tenant, matter, rotate)

    def recover_root_wrapping(self, tenant_id: str, matter_id: str, recovery_secret: str) -> dict[str, Any]:
        """Re-wrap active/retired keys from an enrolled recovery secret.

        This does not reverse deliberate revocation or cryptographic deletion.
        """

        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")

        def recover(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None or state.get("status") != "active":
                raise MatterKeyHierarchyError("matter_key_recovery_unavailable")
            recovery = dict(state.get("recovery") or {})
            if not recovery.get("enabled"):
                raise MatterKeyHierarchyError("recovery_not_enrolled")
            salt = _decode(recovery.get("salt"), field="recovery_salt")
            wrappers = dict(recovery.get("wrapped_keys") or {})
            for row in state.get("keys") or []:
                if not isinstance(row, dict) or row.get("status") not in {"active", "retired"}:
                    continue
                key_id = str(row.get("key_id") or "")
                key = self._unwrap_recovery(
                    dict(wrappers.get(key_id) or {}), recovery_secret, salt, tenant, matter, key_id
                )
                row["wrapped_key"] = self._wrap_root(key, tenant, matter, key_id)
            self._event(state, "matter_key_root_wrapping_recovered", key_id=str(state.get("active_key_id") or ""))
            return self._public_status(state), True

        return self._mutate(tenant, matter, recover, create_if_missing=False)

    def revoke(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")

        def revoke(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None:
                raise MatterKeyHierarchyError("matter_key_unavailable")
            if state.get("status") == "cryptographically_deleted":
                raise MatterKeyHierarchyError("matter_key_cryptographically_deleted")
            for row in state.get("keys") or []:
                if isinstance(row, dict) and row.get("status") in {"active", "retired"}:
                    row["status"] = "revoked"
            state["status"] = "revoked"
            state["active_key_id"] = None
            self._event(state, "matter_key_revoked")
            return self._public_status(state), True

        return self._mutate(tenant, matter, revoke, create_if_missing=False)

    def cryptographic_delete(
        self, tenant_id: str, matter_id: str, *, approved: bool, confirmation: str
    ) -> dict[str, Any]:
        tenant = _validate_identifier(tenant_id, field="tenant_id")
        matter = _validate_identifier(matter_id, field="matter_id")
        if not approved or not hmac.compare_digest(str(confirmation or ""), f"DELETE {matter}"):
            raise MatterKeyHierarchyError("cryptographic_delete_confirmation_required")

        def destroy(state: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if state is None:
                raise MatterKeyHierarchyError("matter_key_unavailable")
            if state.get("status") == "cryptographically_deleted":
                return self._public_status(state), False
            for row in state.get("keys") or []:
                if isinstance(row, dict):
                    row["wrapped_key"] = None
                    row["status"] = "destroyed"
            state["recovery"] = {"enabled": False, "destroyed": True}
            state["active_key_id"] = None
            state["status"] = "cryptographically_deleted"
            self._event(state, "matter_key_cryptographically_deleted")
            return self._public_status(state), True

        return self._mutate(tenant, matter, destroy, create_if_missing=False)


__all__ = ["MatterKeyHierarchy", "MatterKeyHierarchyError"]
