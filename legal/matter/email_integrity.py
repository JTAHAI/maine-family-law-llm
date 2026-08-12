"""Encrypted email-export metadata ledger; it never sends mail or decides authenticity."""

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


def _text(value: Any, *, maximum: int = 8_000) -> str:
    normalized = str(value or "").strip()
    if len(normalized) > maximum:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return normalized


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class EmailIntegrityStore:
    """Case-scoped, encrypted email export ledger with tamper-evident history."""

    schema = "maine_family_law_llm.email_integrity.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "40_EMAIL_INTEGRITY"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("email_store_unavailable", 409)
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY")
        self.encryptor = LocalEnvelopeEncryptor(key or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "email.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".email.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "exports": [],
                "history": [],
                "revision": 0,
            }
        try:
            encrypted = strict_json_load_path(
                self.path, max_bytes=8 * 1024 * 1024, require_object=True
            )
            value = self.encryptor.decrypt_json(encrypted)
        except Exception as exc:
            raise IntakeWorkbenchError("email_store_unavailable", 409) from exc
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
                "event_id": f"email_{uuid.uuid4().hex}",
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
                "mail_send": False,
                "authenticity": "not_determined",
                "delivery": "not_determined",
            }
        )
        return value

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("exports")
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
            raise IntakeWorkbenchError("exports_invalid")
        identifiers = [_identifier(row.get("export_id"), "export_id") for row in rows]

        def update(value: dict[str, Any]) -> dict[str, Any]:
            for row, export_id in zip(rows, identifiers, strict=True):
                attachments = row.get("attachment_hashes", [])
                if not isinstance(attachments, list):
                    raise IntakeWorkbenchError("attachment_hashes_invalid")
                value["exports"].append(
                    {
                        "export_id": export_id,
                        "source_hash": _text(row.get("source_hash"), maximum=128),
                        "header_hash": _text(row.get("header_hash"), maximum=128),
                        "attachment_hashes": [_text(item, maximum=128) for item in attachments],
                        "format": _text(row.get("format"), maximum=64),
                        "source_ref": row.get("source_ref") or {},
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mutate("email_export_added", identifiers, update)

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "exports_hash": _hash(value["exports"]),
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
