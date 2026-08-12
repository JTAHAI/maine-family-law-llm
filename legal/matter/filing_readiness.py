"""Encrypted filing-package checklist that never files or certifies court readiness."""

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


class FilingReadinessStore:
    """Case-scoped filing checklist with explicit no-submission/no-certification controls."""

    schema = "maine_family_law_llm.filing_readiness.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "38_FILING_READINESS"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("filing_store_unavailable", 409)
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY")
        self.encryptor = LocalEnvelopeEncryptor(key or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "filing.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".filing.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "packages": [],
                "history": [],
                "revision": 0,
            }
        try:
            encrypted = strict_json_load_path(
                self.path, max_bytes=8 * 1024 * 1024, require_object=True
            )
            value = self.encryptor.decrypt_json(encrypted)
        except Exception as exc:
            raise IntakeWorkbenchError("filing_store_unavailable", 409) from exc
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
                "event_id": f"filing_{uuid.uuid4().hex}",
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
                "automatic_filing": False,
                "filing_readiness": "not_determined",
                "mrecs_submission": False,
            }
        )
        return value

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("packages")
        if not isinstance(rows, list) or not rows or not all(
            isinstance(row, dict) for row in rows
        ):
            raise IntakeWorkbenchError("packages_invalid")
        identifiers = [_identifier(row.get("package_id"), "package_id") for row in rows]

        def update(value: dict[str, Any]) -> dict[str, Any]:
            for row, package_id in zip(rows, identifiers, strict=True):
                document_values = row.get("document_ids", [])
                if not isinstance(document_values, list):
                    raise IntakeWorkbenchError("document_ids_invalid")
                value["packages"].append(
                    {
                        "package_id": package_id,
                        "document_ids": [
                            _identifier(item, "document_id") for item in document_values
                        ],
                        "court_safe_id": _text(row.get("court_safe_id"), maximum=128),
                        "service_proof_candidate": _text(
                            row.get("service_proof_candidate"), maximum=128
                        ),
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mutate("package_added", identifiers, update)

    def validate(self, package_id: Any) -> dict[str, Any]:
        normalized = _identifier(package_id, "package_id")
        package = next(
            (item for item in self._load()["packages"] if item["package_id"] == normalized),
            None,
        )
        if package is None:
            raise IntakeWorkbenchError("package_not_found", 404)
        blockers: list[str] = []
        if not package["document_ids"]:
            blockers.append("missing_documents")
        if not package["court_safe_id"]:
            blockers.append("missing_court")
        if not package["service_proof_candidate"]:
            blockers.append("missing_service_proof")
        return {
            "status": "review_required",
            "package_id": package["package_id"],
            "blockers": blockers,
            "filing_readiness": "not_determined",
            "automatic_filing": False,
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "packages_hash": _hash(value["packages"]),
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
