"""Encrypted reviewer-handoff manifests; no silent sharing or external upload."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")


def _identifier(value: Any, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _ID.fullmatch(normalized):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return normalized


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ReviewerHandoffStore:
    """A case-scoped manifest ledger; generated bundles always require a human reviewer."""

    schema = "maine_family_law_llm.reviewer_handoff.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "41_REVIEWER_HANDOFF"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("handoff_store_unavailable", 409)
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY")
        self.encryptor = LocalEnvelopeEncryptor(key or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "handoffs.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".handoffs.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "handoffs": [],
                "history": [],
                "revision": 0,
            }
        try:
            encrypted = strict_json_load_path(
                self.path, max_bytes=8 * 1024 * 1024, require_object=True
            )
            value = self.encryptor.decrypt_json(encrypted)
        except Exception as exc:
            raise IntakeWorkbenchError("handoff_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        encrypted = self.encryptor.encrypt_json(value)
        atomic_write_bytes(self.path, json.dumps(encrypted, sort_keys=True).encode(), mode=0o600)

    def _mutate(
        self,
        action: str,
        identifiers: list[str],
        update: Callable[[dict[str, Any]], Any],
    ) -> Any:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {
                "event_id": f"handoff_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": identifiers,
                "previous_hash": value["history"][-1]["hash"] if value["history"] else "",
                "review_required": True,
            }
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = deepcopy(self._load())
        value.pop("scope", None)
        value.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "automatic_share": False,
                "external_upload": False,
                "bundle_generation": "manifest_only",
            }
        )
        return value

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        handoff_id = _identifier(payload.get("handoff_id"), "handoff_id")
        record_values = payload.get("record_ids", [])
        if not isinstance(record_values, list):
            raise IntakeWorkbenchError("handoff_records_invalid")
        record_ids = [_identifier(item, "record_id") for item in record_values]
        if not record_ids or len(record_ids) > 500:
            raise IntakeWorkbenchError("handoff_records_invalid")
        reviewer_safe_id = _identifier(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        purpose = str(payload.get("purpose") or "").strip()
        if len(purpose) > 1_000:
            raise IntakeWorkbenchError("text_limit_exceeded")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["handoff_id"] == handoff_id for item in value["handoffs"]):
                raise IntakeWorkbenchError("duplicate_handoff_id", 409)
            manifest = {
                "handoff_id": handoff_id,
                "record_ids": record_ids,
                "reviewer_safe_id": reviewer_safe_id,
                "purpose": purpose,
                "encrypted_manifest": True,
                "review_required": True,
                "created_at": _now(),
            }
            manifest["manifest_hash"] = _hash(manifest)
            value["handoffs"].append(manifest)
            return deepcopy(manifest)

        return self._mutate("handoff_manifest_added", [handoff_id, *record_ids], update)

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "handoffs_hash": _hash(value["handoffs"]),
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
