"""Encrypted, source-bound matter fact pins.

Pins are review aids, never findings.  They retain only a user supplied label
and an exact source locator, and keep an append-only, hash-linked local audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SOURCE_ID = re.compile(r"[A-Za-z0-9_.:@/-]{1,256}\Z")
_ROLES = {"self_represented", "legal_aid", "attorney", "reviewer"}
_DISPUTE = {"undisputed", "disputed", "unclear"}
_LANES = {"private_record", "legal_authority"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _id(value: Any, name: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _ID.fullmatch(normalized):
        raise IntakeWorkbenchError(f"{name}_invalid")
    return normalized


def _text(value: Any, name: str, limit: int = 1000) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise IntakeWorkbenchError(f"{name}_required")
    if len(normalized) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return normalized


class FactPinStore:
    """Matter-scoped encrypted pins with source drill-down metadata."""

    schema = "maine_family_law_llm.fact_pins.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "31_FACT_PINS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("fact_pin_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode("utf-8")).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "fact_pins.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".fact_pins.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "pins": [], "history": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("fact_pin_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode("utf-8"), mode=0o600)

    def _mutate(self, action: str, ids: list[str], operation):
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = operation(value)
            event = {"event_id": f"fact_pin_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": ids, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = deepcopy(self._load())
        value.pop("scope", None)
        value.update({"status": "review_required", "review_required": True, "local_only": True, "fact_findings": "not_determined", "filing_ready": False})
        return value

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        pin_id = _id(payload.get("pin_id"), "pin_id")
        actor_role = str(payload.get("actor_role") or "").strip().casefold()
        if actor_role not in _ROLES:
            raise IntakeWorkbenchError("fact_pin_role_denied", 403)
        source = payload.get("source_ref") or {}
        source_id = str(source.get("source_id") or "").strip()
        if not _SOURCE_ID.fullmatch(source_id):
            raise IntakeWorkbenchError("source_id_invalid")
        source_lane = str(source.get("source_lane") or "").strip().casefold()
        if source_lane not in _LANES:
            raise IntakeWorkbenchError("source_lane_invalid")
        effective_date = str(payload.get("effective_date") or "").strip()
        if effective_date:
            try:
                date.fromisoformat(effective_date)
            except ValueError as exc:
                raise IntakeWorkbenchError("effective_date_invalid") from exc
        dispute_status = str(payload.get("dispute_status") or "unclear").strip().casefold()
        if dispute_status not in _DISPUTE:
            raise IntakeWorkbenchError("dispute_status_invalid")
        pin = {"pin_id": pin_id, "label": _text(payload.get("label"), "label", 1000), "effective_date": effective_date or None, "dispute_status": dispute_status, "source_ref": {"source_id": source_id, "source_lane": source_lane, "locator": _text(source.get("locator"), "source_locator", 1000), "source_hash": _text(source.get("source_hash"), "source_hash", 128)}, "actor_role": actor_role, "reviewer_status": "review_required", "created_at": _now()}

        def operation(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["pin_id"] == pin_id for item in value["pins"]):
                raise IntakeWorkbenchError("duplicate_fact_pin_id", 409)
            value["pins"].append(pin)
            return self.get(pin_id, value=value)

        return self._mutate("fact_pin_created", [pin_id, source_id], operation)

    def get(self, pin_id: str, *, value: dict[str, Any] | None = None) -> dict[str, Any]:
        pin_id = _id(pin_id, "pin_id")
        item = next((row for row in (value or self._load())["pins"] if row["pin_id"] == pin_id), None)
        if not item:
            raise IntakeWorkbenchError("fact_pin_not_found", 404)
        return {"pin": deepcopy(item), "source_drill_down": deepcopy(item["source_ref"]), "status": "review_required", "review_required": True, "fact_findings": "not_determined", "filing_ready": False}

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {"revision": value["revision"], "pins_hash": _hash(value["pins"]), "history_hash": _hash(value["history"]), "review_required": True, "issued_at": _now()}
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
