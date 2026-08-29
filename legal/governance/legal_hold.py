"""Encrypted, audited legal-hold controls for selected matter artifact IDs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_MAX_STATE_BYTES = 1024 * 1024
_MAX_HOLDS = 300


class LegalHoldError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _safe(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text):
        raise LegalHoldError(code)
    return text


def _root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "legal-holds"
    return Path(os.environ.get("MFL_LEGAL_HOLD_ROOT") or default).resolve()


class LegalHoldStore:
    """Per-tenant encrypted hold registers with non-secret, hash-chained audit."""

    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "legal_hold_store_v1", "tenant_id": "", "holds": {}, "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise LegalHoldError("legal_hold_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "legal_hold_store_v1" or not isinstance(state.get("holds"), dict):
            raise LegalHoldError("legal_hold_store_unavailable")
        return state

    def _write(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _audit(state: dict[str, Any], *, tenant_id: str, event_type: str, hold_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
        basis = {"event_type": event_type, "recorded_at": _now(), "tenant_id": tenant_id, "hold_id": hold_id, "payload_hash": _digest(payload), "previous_hash": previous}
        event = {**basis, "event_hash": _digest(basis)}
        state["audit"] = [*list(state.get("audit") or []), event][-_MAX_HOLDS:]
        return event

    @staticmethod
    def _view(record: dict[str, Any], audit: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"hold_id": record["hold_id"], "matter_scope": record["matter_scope"], "artifact_ids": list(record["artifact_ids"]), "artifact_count": len(record["artifact_ids"]), "authority_ref": record["authority_ref"], "status": record["status"], "placed_at": record["placed_at"], "released_at": record.get("released_at", ""), "source_drill_down": {"authority_ref": record["authority_ref"], "artifact_ids": list(record["artifact_ids"]), "audit_event_hash": (audit or {}).get("event_hash", ""), "review_required": True}, "review_required": True}

    def place(self, *, tenant_id: str, matter_scope: str, hold_id: str, artifact_ids: list[Any], authority_ref: str) -> dict[str, Any]:
        tenant = _safe(tenant_id, "legal_hold_tenant_invalid")
        matter = _safe(matter_scope, "legal_hold_matter_scope_invalid")
        hold = _safe(hold_id, "legal_hold_id_invalid")
        authority = _safe(authority_ref, "legal_hold_authority_ref_invalid")
        artifacts = sorted(set(_safe(item, "legal_hold_artifact_id_invalid") for item in artifact_ids))
        if not artifacts or len(artifacts) > 200:
            raise LegalHoldError("legal_hold_artifact_ids_invalid")
        path = self._path(tenant)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant:
                raise LegalHoldError("legal_hold_tenant_mismatch")
            if hold in state["holds"]:
                raise LegalHoldError("legal_hold_id_exists")
            record = {"hold_id": hold, "matter_scope": matter, "artifact_ids": artifacts, "authority_ref": authority, "status": "active", "placed_at": _now(), "released_at": "", "release_authority_ref": ""}
            state["tenant_id"] = tenant; state["holds"][hold] = record
            audit = self._audit(state, tenant_id=tenant, event_type="legal_hold_placed", hold_id=hold, payload=record); self._write(path, state)
        return {"schema_version": "legal_hold_v1", "status": "review_required", "hold": self._view(record, audit), "deletion_prevented": True, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "This preserves only the selected artifact identifiers. It does not determine legal obligations or replace an authorized legal-hold instruction."}

    def list(self, *, tenant_id: str, matter_scope: str) -> dict[str, Any]:
        tenant = _safe(tenant_id, "legal_hold_tenant_invalid"); matter = _safe(matter_scope, "legal_hold_matter_scope_invalid")
        state = self._load(self._path(tenant))
        rows = [self._view(record) for record in state["holds"].values() if isinstance(record, dict) and record.get("matter_scope") == matter]
        rows.sort(key=lambda row: (row["status"] != "active", row["hold_id"]))
        return {"schema_version": "legal_hold_list_v1", "status": "review_required", "matter_scope": matter, "holds": rows, "active_hold_count": sum(1 for row in rows if row["status"] == "active"), "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True}

    def release(self, *, tenant_id: str, matter_scope: str, hold_id: str, release_authority_ref: str) -> dict[str, Any]:
        tenant = _safe(tenant_id, "legal_hold_tenant_invalid"); matter = _safe(matter_scope, "legal_hold_matter_scope_invalid"); hold = _safe(hold_id, "legal_hold_id_invalid"); authority = _safe(release_authority_ref, "legal_hold_release_authority_ref_invalid")
        path = self._path(tenant)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); record = state["holds"].get(hold)
            if not isinstance(record, dict) or record.get("matter_scope") != matter:
                raise LegalHoldError("legal_hold_not_found")
            if record.get("status") != "active":
                raise LegalHoldError("legal_hold_not_active")
            record["status"] = "released"; record["released_at"] = _now(); record["release_authority_ref"] = authority
            audit = self._audit(state, tenant_id=tenant, event_type="legal_hold_released", hold_id=hold, payload=record); self._write(path, state)
        return {"schema_version": "legal_hold_v1", "status": "review_required", "hold": self._view(record, audit), "deletion_prevented": False, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "Release is recorded as review-required and does not itself delete any artifact."}

    def deletion_check(self, *, matter_scope: str, artifact_id: str) -> dict[str, Any]:
        """Fail closed if any encrypted tenant register holds this local artifact.

        The result deliberately reveals no tenant, authority, or artifact content
        beyond the caller's artifact identifier.
        """

        matter = _safe(matter_scope, "legal_hold_matter_scope_invalid"); artifact = _safe(artifact_id, "legal_hold_artifact_id_invalid")
        blockers: list[str] = []
        if self.root.is_dir():
            for path in sorted(self.root.glob("*.json.enc")):
                try:
                    state = self._load(path)
                except LegalHoldError:
                    blockers.append("legal_hold_register_unavailable")
                    continue
                for record in state.get("holds", {}).values():
                    if isinstance(record, dict) and record.get("status") == "active" and record.get("matter_scope") == matter and artifact in set(record.get("artifact_ids") or []):
                        blockers.append("legal_hold_active")
                        break
        return {"allowed": not blockers, "status": "clear" if not blockers else "blocked", "blockers": sorted(set(blockers)), "review_required": True}


__all__ = ["LegalHoldError", "LegalHoldStore"]
