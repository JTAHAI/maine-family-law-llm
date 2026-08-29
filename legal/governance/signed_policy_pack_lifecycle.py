"""Encrypted, tenant-scoped lifecycle for externally signed policy packs.

Only externally provisioned Ed25519 public keys can make a draft eligible for
activation.  This keeps the local workbench from inventing governance approval
or manufacturing a signing credential.
"""

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
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]{1,48})?$")
_MAX_STATE_BYTES = 1024 * 1024
_MAX_PACKS = 100
_REQUIRED_CONTROLS = {
    "local_only": True,
    "review_required": True,
    "filing_gate_required": True,
    "no_unapproved_external_provider": True,
    "no_cross_matter_access": True,
}


class SignedPolicyPackError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _safe(value: Any, error: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text):
        raise SignedPolicyPackError(error)
    return text


def _root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "signed-policy-packs"
    return Path(os.environ.get("MFL_SIGNED_POLICY_PACK_ROOT") or default).resolve()


def _trust_path(project_root: str | Path) -> Path:
    return Path(os.environ.get("MFL_POLICY_PACK_TRUST_CONFIG") or Path(project_root).resolve() / "configs" / "policy_pack_trust.json").resolve()


def signable_payload(pack: dict[str, Any]) -> bytes:
    return _canonical({"schema_version": "signed_policy_pack_payload_v1", "pack_id": pack["pack_id"], "version": pack["version"], "parent_pack_hash": pack["parent_pack_hash"], "controls": pack["controls"]})


def _validate_controls(value: Any) -> tuple[dict[str, bool], list[str]]:
    controls = dict(value or {}) if isinstance(value, dict) else {}
    blockers: list[str] = []
    if set(controls) != set(_REQUIRED_CONTROLS):
        blockers.append("policy_pack_controls_incomplete")
    normalized: dict[str, bool] = {}
    for name, required in _REQUIRED_CONTROLS.items():
        current = controls.get(name)
        if type(current) is not bool:
            blockers.append(f"policy_pack_control_boolean_required:{name}")
            normalized[name] = False
        else:
            normalized[name] = current
        if current is not required:
            blockers.append(f"policy_pack_control_weakening_refused:{name}")
    return normalized, sorted(set(blockers))


def _verify_signature(pack: dict[str, Any], signature: dict[str, Any], trust_config: Path) -> dict[str, Any]:
    blockers: list[str] = []
    try:
        trust = strict_json_load_path(trust_config, max_bytes=256 * 1024, require_object=True)
    except Exception:
        trust = {}
        blockers.append("policy_pack_trust_config_unavailable")
    keys = trust.get("trusted_keys") if isinstance(trust, dict) else None
    if not isinstance(keys, dict):
        blockers.append("policy_pack_trust_config_invalid")
        keys = {}
    key_id = str(signature.get("key_id") or "").strip()
    encoded_key = keys.get(key_id)
    if not isinstance(encoded_key, str) or not encoded_key:
        blockers.append("policy_pack_signing_key_untrusted")
    else:
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded_key, validate=True))
            encoded_signature = str(signature.get("signature") or "")
            key.verify(base64.b64decode(encoded_signature, validate=True), signable_payload(pack))
        except (ValueError, InvalidSignature):
            blockers.append("policy_pack_signature_invalid")
    return {"status": "verified" if not blockers else "blocked", "key_id": key_id[:100], "signature_present": bool(signature.get("signature")), "trust_config_sha256": _digest(trust_config.read_bytes()) if trust_config.is_file() else "", "blockers": sorted(set(blockers)), "review_required": True}


class SignedPolicyPackStore:
    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None, project_root: str | Path | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.project_root = Path(project_root or os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[2]).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "signed_policy_pack_store_v1", "tenant_id": "", "packs": {}, "active_pack_id": "", "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise SignedPolicyPackError("signed_policy_pack_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "signed_policy_pack_store_v1" or not isinstance(state.get("packs"), dict):
            raise SignedPolicyPackError("signed_policy_pack_store_unavailable")
        return state

    def _write(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _audit(state: dict[str, Any], *, tenant_id: str, event_type: str, pack_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
        basis = {"event_type": event_type, "recorded_at": _now(), "tenant_id": tenant_id, "pack_id": pack_id, "payload_hash": _digest(payload), "previous_hash": previous}
        event = {**basis, "event_hash": _digest(basis)}
        state["audit"] = [*list(state.get("audit") or []), event][-_MAX_PACKS:]
        return event

    def draft(self, *, tenant_id: str, pack_id: str, version: str, controls: dict[str, Any] | None = None) -> dict[str, Any]:
        pack = _safe(pack_id, "signed_policy_pack_id_invalid")
        text_version = str(version or "").strip()
        if not _VERSION.fullmatch(text_version):
            raise SignedPolicyPackError("signed_policy_pack_version_invalid")
        normal_controls, blockers = _validate_controls(_REQUIRED_CONTROLS if controls is None else controls)
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant_id:
                raise SignedPolicyPackError("signed_policy_pack_tenant_mismatch")
            if pack in state["packs"]:
                raise SignedPolicyPackError("signed_policy_pack_id_exists")
            active = state["packs"].get(str(state.get("active_pack_id") or ""), {})
            parent_hash = str(active.get("content_sha256") or "")
            record = {"pack_id": pack, "version": text_version, "controls": normal_controls, "parent_pack_hash": parent_hash, "content_sha256": "", "status": "draft", "validation": {"status": "blocked" if blockers else "valid", "blockers": blockers, "review_required": True}, "signature": {"status": "unverified", "key_id": "", "signature_present": False, "blockers": ["policy_pack_external_signature_required"], "review_required": True}, "history": [], "activated_at": "", "expired_at": "", "rolled_back_at": ""}
            record["content_sha256"] = _digest({key: record[key] for key in ("pack_id", "version", "controls", "parent_pack_hash")})
            record["history"].append({"event": "drafted", "at": _now(), "content_sha256": record["content_sha256"]})
            state["tenant_id"] = tenant_id; state["packs"][pack] = record
            audit = self._audit(state, tenant_id=tenant_id, event_type="signed_policy_pack_drafted", pack_id=pack, payload=record)
            self._write(path, state)
        return self._response(record, audit)

    def _read(self, state: dict[str, Any], pack_id: str) -> dict[str, Any]:
        pack = _safe(pack_id, "signed_policy_pack_id_invalid")
        value = state["packs"].get(pack)
        if not isinstance(value, dict):
            raise SignedPolicyPackError("signed_policy_pack_not_found")
        return value

    @staticmethod
    def _response(record: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": "signed_policy_pack_lifecycle_v1", "status": record.get("status"), "policy_pack": record, "source_drill_down": {"content_sha256": record.get("content_sha256", ""), "parent_pack_hash": record.get("parent_pack_hash", ""), "signature_key_id": (record.get("signature") or {}).get("key_id", ""), "audit_event_hash": audit.get("event_hash", ""), "review_required": True}, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "Policy-pack state is local, encrypted, tenant-scoped, and review-required. It cannot create a signing key or substitute for accountable external approval."}

    def validate(self, *, tenant_id: str, pack_id: str) -> dict[str, Any]:
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = self._read(state, pack_id)
            controls, blockers = _validate_controls(record.get("controls"))
            if controls != record.get("controls"):
                blockers.append("policy_pack_controls_tampered")
            if record.get("content_sha256") != _digest({key: record.get(key) for key in ("pack_id", "version", "controls", "parent_pack_hash")}):
                blockers.append("policy_pack_content_hash_mismatch")
            record["validation"] = {"status": "valid" if not blockers else "blocked", "blockers": sorted(set(blockers)), "review_required": True}
            if record["status"] not in {"active", "expired", "rolled_back"}:
                record["status"] = "validated" if not blockers else "blocked"
            record["history"].append({"event": "validated", "at": _now(), "blockers": sorted(set(blockers))})
            audit = self._audit(state, tenant_id=tenant_id, event_type="signed_policy_pack_validated", pack_id=record["pack_id"], payload=record); self._write(path, state)
        return self._response(record, audit)

    def approve(self, *, tenant_id: str, pack_id: str, signature: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(signature, dict):
            raise SignedPolicyPackError("signed_policy_pack_signature_invalid")
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = self._read(state, pack_id)
            verification = _verify_signature(record, signature, _trust_path(self.project_root))
            record["signature"] = verification
            valid = (record.get("validation") or {}).get("status") == "valid"
            record["status"] = "approved" if valid and verification["status"] == "verified" else "blocked"
            record["history"].append({"event": "signature_checked", "at": _now(), "status": verification["status"], "key_id": verification["key_id"], "blockers": verification["blockers"]})
            audit = self._audit(state, tenant_id=tenant_id, event_type="signed_policy_pack_approval_checked", pack_id=record["pack_id"], payload=record); self._write(path, state)
        return self._response(record, audit)

    def activate(self, *, tenant_id: str, pack_id: str) -> dict[str, Any]:
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = self._read(state, pack_id)
            blockers = list((record.get("validation") or {}).get("blockers") or [])
            if (record.get("signature") or {}).get("status") != "verified": blockers.append("policy_pack_external_signature_required")
            if blockers:
                record["status"] = "blocked"; record["history"].append({"event": "activation_blocked", "at": _now(), "blockers": sorted(set(blockers))})
            else:
                prior = str(state.get("active_pack_id") or "")
                if prior and prior in state["packs"] and prior != record["pack_id"]:
                    state["packs"][prior]["status"] = "superseded"
                    state["packs"][prior]["superseded_by"] = record["pack_id"]
                record["status"] = "active"; record["activated_at"] = _now(); record["prior_active_pack_id"] = prior
                record["history"].append({"event": "activated", "at": record["activated_at"], "prior_active_pack_id": prior})
                state["active_pack_id"] = record["pack_id"]
            audit = self._audit(state, tenant_id=tenant_id, event_type="signed_policy_pack_activation_checked", pack_id=record["pack_id"], payload=record); self._write(path, state)
        return self._response(record, audit)

    def expire(self, *, tenant_id: str, pack_id: str) -> dict[str, Any]:
        return self._terminal(tenant_id=tenant_id, pack_id=pack_id, event="expired")

    def rollback(self, *, tenant_id: str, pack_id: str) -> dict[str, Any]:
        return self._terminal(tenant_id=tenant_id, pack_id=pack_id, event="rolled_back")

    def _terminal(self, *, tenant_id: str, pack_id: str, event: str) -> dict[str, Any]:
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = self._read(state, pack_id)
            record["status"] = event; record[f"{event}_at"] = _now(); record["history"].append({"event": event, "at": record[f"{event}_at"]})
            if state.get("active_pack_id") == record["pack_id"]:
                state["active_pack_id"] = ""
                if event == "rolled_back":
                    prior_id = str(record.get("prior_active_pack_id") or "")
                    prior = state["packs"].get(prior_id)
                    prior_eligible = isinstance(prior, dict) and (prior.get("signature") or {}).get("status") == "verified" and not list((prior.get("validation") or {}).get("blockers") or [])
                    if prior_eligible:
                        prior["status"] = "active"; prior["reactivated_at"] = _now()
                        prior.setdefault("history", []).append({"event": "reactivated_by_rollback", "at": prior["reactivated_at"], "rolled_back_pack_id": record["pack_id"]})
                        state["active_pack_id"] = prior_id
                    else:
                        record.setdefault("rollback_blockers", []).append("prior_signed_policy_pack_not_eligible_for_reactivation")
            audit = self._audit(state, tenant_id=tenant_id, event_type=f"signed_policy_pack_{event}", pack_id=record["pack_id"], payload=record); self._write(path, state)
        return self._response(record, audit)

    def diff(self, *, tenant_id: str, pack_id: str) -> dict[str, Any]:
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = self._read(state, pack_id)
            parent = next((item for item in state["packs"].values() if isinstance(item, dict) and item.get("content_sha256") == record.get("parent_pack_hash")), None)
            before = dict(parent.get("controls") or {}) if isinstance(parent, dict) else dict(_REQUIRED_CONTROLS)
            after = dict(record.get("controls") or {})
            diff = {name: {"before": before.get(name), "after": after.get(name)} for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
            audit = self._audit(state, tenant_id=tenant_id, event_type="signed_policy_pack_diff_inspected", pack_id=record["pack_id"], payload={"content_sha256": record.get("content_sha256"), "diff": diff}); self._write(path, state)
        return {**self._response(record, audit), "diff": diff, "base": {"content_sha256": str((parent or {}).get("content_sha256") or "baseline_controls"), "found": isinstance(parent, dict)}}


__all__ = ["SignedPolicyPackError", "SignedPolicyPackStore", "signable_payload"]
