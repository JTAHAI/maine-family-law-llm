"""Privacy-safe enterprise configuration manifest and external signature verifier."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_CONFIG_FILES = ("maine_enterprise_security_controls.json", "maine_governance_compliance_packet.json", "maine_retention_policy.json", "policy_pack_trust.json", "retention_engine_approval.json", "store_update_trust.json")
_EVIDENCE_FILES = ("pass163_separation_of_duties_acceptance.json", "pass164_signed_policy_pack_lifecycle_acceptance.json", "pass165_legal_hold_controls_acceptance.json", "pass166_retention_policy_engine_acceptance.json", "pass167_audit_verification_console_acceptance.json")
_MAX_STATE_BYTES = 512 * 1024


class ConfigurationExportError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def signed_payload(manifest: dict[str, Any]) -> bytes:
    value = dict(manifest); value.pop("signature", None); return _canonical(value)


def _default_root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "configuration-exports"
    return Path(os.environ.get("MFL_CONFIGURATION_EXPORT_ROOT") or default).resolve()


class ConfigurationExportService:
    def __init__(self, project_root: str | Path, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.project_root = Path(project_root).resolve(); self.root = Path(root or _default_root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists(): return {"schema_version": "configuration_export_receipts_v1", "tenant_id": "", "receipts": [], "audit": []}
        try: state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc: raise ConfigurationExportError("configuration_export_receipt_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "configuration_export_receipts_v1": raise ConfigurationExportError("configuration_export_receipt_store_unavailable")
        return state

    def build(self, *, tenant_id: str) -> dict[str, Any]:
        configs = []
        for name in _CONFIG_FILES:
            path = self.project_root / "configs" / name
            configs.append({"config_id": name.removesuffix(".json"), "present": path.is_file(), "sha256": _digest(path.read_bytes()) if path.is_file() else ""})
        evidence = []
        for name in _EVIDENCE_FILES:
            path = self.project_root / "dist" / "ga_today" / "evidence" / name
            try: payload = strict_json_load_path(path, max_bytes=2 * 1024 * 1024, require_object=True); status = str(payload.get("status") or "unknown")
            except Exception: status = "unavailable"
            evidence.append({"evidence_id": name.removesuffix(".json"), "status": status[:60], "sha256": _digest(path.read_bytes()) if path.is_file() else ""})
        manifest = {"schema_version": "enterprise_configuration_manifest_v1", "generated_at": _now(), "tenant_scope": tenant_id, "configuration": configs, "compliance_evidence": evidence, "privacy": {"private_record_content_included": False, "matter_database_included": False, "credentials_included": False, "raw_paths_included": False}, "delivery": {"network_used": False, "export_written_to_disk": False}, "review_required": True, "signature": {"status": "external_signature_required", "key_id": "", "signature_present": False}}
        manifest["manifest_sha256"] = _digest({key: value for key, value in manifest.items() if key not in {"signature", "manifest_sha256"}})
        return manifest

    def verify_and_receipt(self, *, manifest: dict[str, Any], tenant_id: str, signature: dict[str, Any]) -> dict[str, Any]:
        if manifest.get("tenant_scope") != tenant_id or (manifest.get("privacy") or {}).get("private_record_content_included") is not False: raise ConfigurationExportError("configuration_export_scope_invalid")
        current = self.build(tenant_id=tenant_id)
        for field in ("schema_version", "configuration", "compliance_evidence", "privacy", "delivery"):
            if manifest.get(field) != current.get(field):
                raise ConfigurationExportError("configuration_export_manifest_stale_or_mismatched")
        trust_path = Path(os.environ.get("MFL_CONFIGURATION_EXPORT_TRUST") or self.project_root / "configs" / "enterprise_configuration_export_trust.json").resolve()
        try: trust = strict_json_load_path(trust_path, max_bytes=256 * 1024, require_object=True)
        except Exception: trust = {}
        key_id = str(signature.get("key_id") or "").strip(); keys = trust.get("trusted_keys") if isinstance(trust, dict) else {}; encoded = keys.get(key_id) if isinstance(keys, dict) else None
        blockers: list[str] = []
        if not isinstance(encoded, str) or not encoded: blockers.append("configuration_export_signing_key_untrusted")
        else:
            try: Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded, validate=True)).verify(base64.b64decode(str(signature.get("signature") or ""), validate=True), signed_payload(manifest))
            except (ValueError, InvalidSignature): blockers.append("configuration_export_signature_invalid")
        verified = not blockers
        view = {**manifest, "signature": {"status": "verified" if verified else "blocked", "key_id": key_id[:100], "signature_present": bool(signature.get("signature")), "blockers": blockers, "trust_config_sha256": _digest(trust_path.read_bytes()) if trust_path.is_file() else ""}}
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); existing = str(state.get("tenant_id") or "")
            if existing and existing != tenant_id: raise ConfigurationExportError("configuration_export_tenant_mismatch")
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or ""); manifest_hash = _digest(view)
            basis = {"event_type": "configuration_manifest_signature_checked", "tenant_id": tenant_id, "manifest_hash": manifest_hash, "previous_hash": previous}; event = {**basis, "event_hash": _digest(basis)}
            receipt = {"receipt_id": f"config_export_{event['event_hash'][:24]}", "manifest_hash": manifest_hash, "signature_status": view["signature"]["status"], "review_required": True}
            state["tenant_id"] = tenant_id; state["receipts"] = [*list(state.get("receipts") or []), receipt][-160:]; state["audit"] = [*list(state.get("audit") or []), event][-160:]
            path.parent.mkdir(parents=True, exist_ok=True); atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"manifest": view, "receipt": receipt, "network_used": False, "review_required": True}


__all__ = ["ConfigurationExportError", "ConfigurationExportService", "signed_payload"]
