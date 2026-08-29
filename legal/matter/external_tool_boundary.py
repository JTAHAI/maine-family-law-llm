"""Local, encrypted receipts for user-controlled external-tool boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DESTINATIONS = {"email", "cloud_storage", "court_portal", "local_tool", "other"}


def _id(value: Any, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _ID.fullmatch(normalized):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return normalized


def _text(value: Any, field: str, maximum: int) -> str:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(normalized) > maximum:
        raise IntakeWorkbenchError(f"{field}_limit_exceeded")
    return normalized


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ExternalToolBoundaryStore:
    """Receipts declare a boundary; they never execute or verify a transfer."""

    schema = "maine_family_law_llm.external_tool_boundary.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "52_EXTERNAL_TOOL_BOUNDARIES"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("external_tool_boundary_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "receipts.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".receipts.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "receipts": [], "history": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("external_tool_boundary_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, identifiers: list[str], update: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {"event_id": f"external_boundary_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": identifiers, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = self._load()
        fields = ("receipt_id", "export_id", "export_hash", "destination_class", "transfer_status", "review_required", "created_at", "receipt_hash")
        return {"receipts": [{key: item[key] for key in fields} for item in value["receipts"]], "revision": value["revision"], "status": "review_required", "review_required": True, "local_only": True, "network_action": False, "destination_address_stored": False}

    def get(self, receipt_id: str) -> dict[str, Any]:
        item_id = _id(receipt_id, "external_boundary_receipt_id")
        item = next((item for item in self._load()["receipts"] if item["receipt_id"] == item_id), None)
        if item is None:
            raise IntakeWorkbenchError("external_boundary_receipt_not_found", 404)
        return {"receipt": item, "status": "review_required", "local_only": True, "network_action": False, "destination_address_stored": False}

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        receipt_id = _id(payload.get("receipt_id"), "external_boundary_receipt_id")
        export_id = _id(payload.get("export_id"), "external_boundary_export_id")
        actor_safe_id = _id(payload.get("actor_safe_id"), "external_boundary_actor_safe_id")
        export_hash = str(payload.get("export_hash") or "").strip().casefold()
        if not _SHA256.fullmatch(export_hash):
            raise IntakeWorkbenchError("external_boundary_export_hash_invalid")
        destination = str(payload.get("destination_class") or "").strip().casefold()
        if destination not in _DESTINATIONS:
            raise IntakeWorkbenchError("external_boundary_destination_class_invalid")
        if payload.get("privacy_risk_acknowledged") is not True:
            raise IntakeWorkbenchError("external_boundary_privacy_acknowledgement_required", 409)
        source_refs = payload.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs or len(source_refs) > 50:
            raise IntakeWorkbenchError("external_boundary_source_refs_invalid")
        sources: list[dict[str, Any]] = []
        for source in source_refs:
            if not isinstance(source, dict):
                raise IntakeWorkbenchError("external_boundary_source_refs_invalid")
            source_hash = str(source.get("source_hash") or "").strip().casefold()
            locator = source.get("source_ref")
            if not _SHA256.fullmatch(source_hash) or not isinstance(locator, dict) or not any(str(locator.get(key) or "").strip() for key in ("record_id", "source_id", "artifact_id")):
                raise IntakeWorkbenchError("external_boundary_source_refs_invalid")
            sources.append({"source_hash": source_hash, "source_ref": {str(key): str(value)[:240] for key, value in locator.items() if key in {"record_id", "source_id", "artifact_id", "span", "page"}}})
        status = "self_reported_transfer_unverified" if payload.get("self_reported_external_transfer") is True else "planned_not_performed"
        receipt = {"receipt_id": receipt_id, "export_id": export_id, "export_hash": export_hash, "purpose": _text(payload.get("purpose"), "external_boundary_purpose", 600), "actor_safe_id": actor_safe_id, "destination_class": destination, "source_refs": sources, "privacy_risk_acknowledged": True, "transfer_status": status, "review_required": True, "network_action": False, "destination_address_stored": False, "created_at": _now()}
        receipt["receipt_hash"] = _hash(receipt)

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["receipt_id"] == receipt_id for item in value["receipts"]):
                raise IntakeWorkbenchError("external_boundary_receipt_exists", 409)
            value["receipts"].append(receipt)
            return {"receipt": receipt, "status": "review_required", "local_only": True, "network_action": False, "notice": "This receipt records a declared boundary only. The application did not transfer, verify, or retain a destination address."}

        return self._mutate("external_tool_boundary_recorded", [receipt_id, export_id, *[source["source_ref"].get("record_id", "source") for source in sources]], update)
