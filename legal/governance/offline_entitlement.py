"""Offline-only signed entitlement verification with no telemetry or matter access."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_MAX_STATE_BYTES = 512 * 1024


class OfflineEntitlementError(ValueError):
    pass


def _canonical(value: Any) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
def _digest(value: Any) -> str: return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()
def _now() -> str: return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def signed_payload(entitlement: dict[str, Any]) -> bytes:
    value = dict(entitlement); value.pop("signature", None); return _canonical(value)


class OfflineEntitlementService:
    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None, project_root: str | Path | None = None) -> None:
        default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "offline-entitlements"
        self.root = Path(root or os.environ.get("MFL_OFFLINE_ENTITLEMENT_ROOT") or default).resolve(); self.project_root = Path(project_root or os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[2]).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _trust(self) -> tuple[dict[str, Any], Path]:
        path = Path(os.environ.get("MFL_OFFLINE_ENTITLEMENT_TRUST") or self.project_root / "configs" / "offline_entitlement_trust.json").resolve()
        try: return strict_json_load_path(path, max_bytes=256 * 1024, require_object=True), path
        except Exception: return {}, path

    def _path(self, tenant_id: str) -> Path: return self.root / f"{_digest(tenant_id)[:32]}.json.enc"
    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists(): return {"schema_version": "offline_entitlement_state_v1", "tenant_id": "", "entitlement": {}, "audit": []}
        try: state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc: raise OfflineEntitlementError("offline_entitlement_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "offline_entitlement_state_v1": raise OfflineEntitlementError("offline_entitlement_store_unavailable")
        return state

    def status(self, *, tenant_id: str) -> dict[str, Any]:
        trust, path = self._trust(); commercial = trust.get("commercial_mode") is True; state = self._load(self._path(tenant_id))
        entitlement = dict(state.get("entitlement") or {})
        return {"schema_version": "offline_entitlement_status_v1", "status": "foss_no_entitlement_required" if not commercial else str(entitlement.get("status") or "entitlement_required"), "commercial_mode": commercial, "entitlement": {"entitlement_id": str(entitlement.get("entitlement_id") or ""), "subject_ref": str(entitlement.get("subject_ref") or ""), "expires_at": str(entitlement.get("expires_at") or ""), "feature_tiers": list(entitlement.get("feature_tiers") or []), "signature_status": str(entitlement.get("signature_status") or "")}, "boundaries": {"offline_only": True, "telemetry_used": False, "provider_request_used": False, "matter_access_decision": "never", "private_matter_content_included": False}, "trust_config_sha256": _digest(path.read_bytes()) if path.is_file() else "", "review_required": True}

    def verify_and_store(self, *, tenant_id: str, entitlement: dict[str, Any]) -> dict[str, Any]:
        trust, trust_path = self._trust()
        if trust.get("commercial_mode") is not True: return {**self.status(tenant_id=tenant_id), "status": "foss_no_entitlement_required", "blockers": ["commercial_mode_disabled"], "review_required": True}
        for field in ("entitlement_id", "subject_ref"):
            if not _SAFE_ID.fullmatch(str(entitlement.get(field) or "")): raise OfflineEntitlementError(f"offline_entitlement_{field}_invalid")
        try: expires = datetime.fromisoformat(str(entitlement.get("expires_at") or "").replace("Z", "+00:00"))
        except ValueError as exc: raise OfflineEntitlementError("offline_entitlement_expiry_invalid") from exc
        tiers = [str(value) for value in entitlement.get("feature_tiers") or []]
        if len(tiers) > 30 or any(not _SAFE_ID.fullmatch(value) for value in tiers): raise OfflineEntitlementError("offline_entitlement_tiers_invalid")
        blockers: list[str] = []
        if entitlement.get("telemetry_allowed") is not False: blockers.append("offline_entitlement_telemetry_refused")
        keys = trust.get("trusted_keys") if isinstance(trust, dict) else {}; key_id = str(entitlement.get("key_id") or ""); encoded = keys.get(key_id) if isinstance(keys, dict) else None
        if not isinstance(encoded, str) or not encoded: blockers.append("offline_entitlement_signing_key_untrusted")
        else:
            try: Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded, validate=True)).verify(base64.b64decode(str(entitlement.get("signature") or ""), validate=True), signed_payload(entitlement))
            except (ValueError, InvalidSignature): blockers.append("offline_entitlement_signature_invalid")
        if expires <= datetime.now(UTC): blockers.append("offline_entitlement_expired")
        record = {"entitlement_id": str(entitlement["entitlement_id"]), "subject_ref": str(entitlement["subject_ref"]), "expires_at": expires.replace(microsecond=0).isoformat().replace("+00:00", "Z"), "feature_tiers": sorted(set(tiers)), "signature_status": "verified" if not blockers else "blocked", "status": "active" if not blockers else "blocked", "key_id": key_id[:100], "telemetry_allowed": False}
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); existing = str(state.get("tenant_id") or "")
            if existing and existing != tenant_id: raise OfflineEntitlementError("offline_entitlement_tenant_mismatch")
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or ""); basis = {"event_type": "offline_entitlement_checked", "tenant_id": tenant_id, "entitlement_hash": _digest(record), "previous_hash": previous, "recorded_at": _now()}; event = {**basis, "event_hash": _digest(basis)}
            state["tenant_id"] = tenant_id; state["entitlement"] = record; state["audit"] = [*list(state.get("audit") or []), event][-160:]
            path.parent.mkdir(parents=True, exist_ok=True); atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {**self.status(tenant_id=tenant_id), "status": record["status"], "blockers": blockers, "audit_receipt": {"event_hash": event["event_hash"], "review_required": True}, "network_used": False, "review_required": True}


__all__ = ["OfflineEntitlementError", "OfflineEntitlementService", "signed_payload"]
