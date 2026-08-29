"""Accessible, explicit local print-preview records for matter review artifacts."""

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


class PrintReviewStore:
    """Encrypted, matter-scoped preview and print-request receipt ledger."""

    schema = "maine_family_law_llm.print_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "51_PRINT_REVIEW"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("print_review_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "previews.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".previews.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "previews": [], "history": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("print_review_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, identifiers: list[str], update: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {"event_id": f"print_review_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": identifiers, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = self._load()
        fields = ("preview_id", "title", "confidentiality_marking", "source_hash", "review_required", "print_request_count", "created_at")
        return {"previews": [{key: item[key] for key in fields} for item in value["previews"]], "revision": value["revision"], "status": "review_required", "review_required": True, "local_only": True, "silent_print": False}

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview_id = _id(payload.get("preview_id"), "print_preview_id")
        if payload.get("privacy_acknowledged") is not True:
            raise IntakeWorkbenchError("print_preview_privacy_acknowledgement_required", 409)
        source_hash = str(payload.get("source_hash") or "").strip().casefold()
        if not _SHA256.fullmatch(source_hash):
            raise IntakeWorkbenchError("print_preview_source_hash_invalid")
        source_ref = payload.get("source_ref")
        if not isinstance(source_ref, dict) or not any(str(source_ref.get(key) or "").strip() for key in ("record_id", "source_id", "artifact_id")):
            raise IntakeWorkbenchError("print_preview_source_locator_required")
        preview = {"preview_id": preview_id, "title": _text(payload.get("title"), "print_preview_title", 240), "confidentiality_marking": _text(payload.get("confidentiality_marking"), "print_preview_confidentiality_marking", 120), "source_hash": source_hash, "source_ref": {str(key): str(value)[:240] for key, value in source_ref.items() if key in {"record_id", "source_id", "artifact_id", "span", "page"}}, "summary": _text(payload.get("summary"), "print_preview_summary", 2_000), "review_required": True, "print_request_count": 0, "created_at": _now()}

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["preview_id"] == preview_id for item in value["previews"]):
                raise IntakeWorkbenchError("print_preview_exists", 409)
            value["previews"].append(preview)
            return {"preview": preview, "status": "review_required", "local_only": True, "silent_print": False, "accessibility": {"high_contrast_print": True, "headers": True, "source_review_footer": True}}

        return self._mutate("print_preview_created", [preview_id], update)

    def get(self, preview_id: str) -> dict[str, Any]:
        item_id = _id(preview_id, "print_preview_id")
        for item in self._load()["previews"]:
            if item["preview_id"] == item_id:
                return {"preview": item, "status": "review_required", "local_only": True, "silent_print": False, "accessibility": {"high_contrast_print": True, "headers": True, "source_review_footer": True}}
        raise IntakeWorkbenchError("print_preview_not_found", 404)

    def request_print(self, preview_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = _id(preview_id, "print_preview_id")
        if payload.get("privacy_acknowledged") is not True:
            raise IntakeWorkbenchError("print_request_privacy_acknowledgement_required", 409)

        def update(value: dict[str, Any]) -> dict[str, Any]:
            item = next((candidate for candidate in value["previews"] if candidate["preview_id"] == item_id), None)
            if item is None:
                raise IntakeWorkbenchError("print_preview_not_found", 404)
            item["print_request_count"] += 1
            receipt = {"preview_id": item_id, "request_number": item["print_request_count"], "source_hash": item["source_hash"], "review_required": True, "system_print_invoked": False, "created_at": _now()}
            receipt["receipt_hash"] = _hash(receipt)
            return {"receipt": receipt, "status": "review_required", "local_only": True, "system_print_invoked": False, "next_action": "User may choose a printer in the browser print dialog."}

        return self._mutate("print_requested", [item_id], update)
