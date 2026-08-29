"""Encrypted, review-first metadata sidecars for active-matter records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_DATE = re.compile(r"(?:unknown|\d{4}-\d{2}-\d{2})\Z")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.,;:/()'&+-]{0,79}\Z")
_CONFIDENTIALITY = {"unknown", "private_record", "restricted", "review_required"}
_DOCUMENT_TYPES = {"unknown", "pleading", "order", "affidavit", "correspondence", "financial_record", "form", "exhibit", "communication"}
_MAX_STATE_BYTES = 8 * 1024 * 1024


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    candidate = str(value or "").strip()
    if not _ID.fullmatch(candidate):
        raise IntakeWorkbenchError(f"metadata_review_{field}_invalid", 422)
    return candidate


def _bounded_text(value: Any, field: str, limit: int = 2000) -> str:
    candidate = str(value or "").strip()
    if len(candidate) > limit:
        raise IntakeWorkbenchError(f"metadata_review_{field}_too_long", 422)
    return candidate


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    labels = payload.get("labels") or []
    if not isinstance(labels, list) or len(labels) > 50:
        raise IntakeWorkbenchError("metadata_review_labels_invalid", 422)
    clean_labels = sorted({str(item).strip() for item in labels if str(item).strip()})
    if any(not _LABEL.fullmatch(item) for item in clean_labels):
        raise IntakeWorkbenchError("metadata_review_label_invalid", 422)
    document_date = str(payload.get("document_date") or "unknown").strip()
    if not _DATE.fullmatch(document_date):
        raise IntakeWorkbenchError("metadata_review_document_date_invalid", 422)
    if document_date != "unknown":
        try:
            datetime.strptime(document_date, "%Y-%m-%d")
        except ValueError as exc:
            raise IntakeWorkbenchError("metadata_review_document_date_invalid", 422) from exc
    custodian = str(payload.get("custodian_safe_id") or "unknown").strip()
    if custodian != "unknown" and not _ID.fullmatch(custodian):
        raise IntakeWorkbenchError("metadata_review_custodian_invalid", 422)
    confidentiality = str(payload.get("confidentiality") or "review_required").strip()
    document_type = str(payload.get("document_type") or "unknown").strip()
    if confidentiality not in _CONFIDENTIALITY:
        raise IntakeWorkbenchError("metadata_review_confidentiality_invalid", 422)
    if document_type not in _DOCUMENT_TYPES:
        raise IntakeWorkbenchError("metadata_review_document_type_invalid", 422)
    return {
        "labels": clean_labels,
        "document_date": document_date,
        "custodian_safe_id": custodian,
        "confidentiality": confidentiality,
        "document_type": document_type,
        "reviewer_notes": _bounded_text(payload.get("reviewer_notes"), "reviewer_notes"),
        "review_required": True,
    }


class MetadataReviewStore:
    schema = "maine_family_law_llm.metadata_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        self.root = self.case_root / "19_EVIDENCE_WORK_PRODUCT" / "metadata-review"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("metadata_review_store_unavailable", 409)
        self.root.mkdir(parents=True, exist_ok=True)
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or LocalEnvelopeEncryptor.development_default)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "metadata-review.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".metadata-review.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "batches": {}, "records": {}, "history": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("metadata_review_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("metadata_review_cross_matter_access_denied", 404)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _binding(row: dict[str, Any]) -> dict[str, str]:
        record_id = _id(row.get("evidence_id"), "record_id")
        source_hash = str(row.get("source_hash") or "").lower()
        if not _HASH.fullmatch(source_hash):
            raise IntakeWorkbenchError("metadata_review_record_source_hash_invalid", 422)
        return {"record_id": record_id, "source_hash": source_hash}

    def apply_batch(self, payload: dict[str, Any], *, records: list[dict[str, Any]]) -> dict[str, Any]:
        batch_id = _id(payload.get("batch_id"), "batch_id")
        requested = [_id(item, "record_id") for item in (payload.get("record_ids") or [])]
        if not requested or len(requested) > 500 or len(set(requested)) != len(requested):
            raise IntakeWorkbenchError("metadata_review_record_ids_invalid", 422)
        by_id = {str(row.get("evidence_id") or ""): row for row in records}
        if any(record_id not in by_id for record_id in requested):
            raise IntakeWorkbenchError("metadata_review_record_not_found_in_active_matter", 404)
        update = _metadata(payload)
        bindings = [self._binding(by_id[record_id]) for record_id in requested]
        with exclusive_file_lock(self.lock):
            state = self._load()
            if batch_id in (state.get("batches") or {}):
                raise IntakeWorkbenchError("metadata_review_batch_id_exists", 409)
            prior_hash = str((state.get("history") or [{}])[-1].get("event_hash") or "")
            event = {"event_id": f"metadata_batch_{uuid.uuid4().hex}", "at": _now(), "action": "metadata_batch_applied", "batch_id": batch_id, "records": bindings, "previous_event_hash": prior_hash, "review_required": True}
            event["event_hash"] = _hash(event)
            batch = {"batch_id": batch_id, "created_at": event["at"], "records": bindings, "update": update, "audit_event_id": event["event_id"], "review_required": True, "notice": "This is reviewer-supplied sidecar metadata. It never changes the original record, source hash, parser output, or legal effect."}
            state.setdefault("batches", {})[batch_id] = batch
            for binding in bindings:
                record_id = binding["record_id"]
                row = dict(state.setdefault("records", {}).get(record_id) or {"record_id": record_id, "history": []})
                row["source_hash"] = binding["source_hash"]
                row["current"] = update
                row.setdefault("history", []).append({"batch_id": batch_id, "audit_event_id": event["event_id"], "update": update, "review_required": True})
                state["records"][record_id] = row
            state.setdefault("history", []).append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {"status": "pass", "batch": deepcopy(batch), "review_required": True}

    def inventory(self, batch_id: str = "") -> dict[str, Any]:
        state = self._load()
        batches = dict(state.get("batches") or {})
        if batch_id:
            row = batches.get(_id(batch_id, "batch_id"))
            if not isinstance(row, dict):
                raise IntakeWorkbenchError("metadata_review_batch_not_found", 404)
            return {"status": "pass", "batch": deepcopy(row), "review_required": True}
        return {"status": "pass", "batches": [deepcopy(item) for _, item in sorted(batches.items())], "review_required": True, "notice": "Metadata edits are encrypted, append-only review sidecars and do not alter original records."}

    def source_binding(self, batch_id: str, record_id: str) -> dict[str, str]:
        batch = self.inventory(batch_id).get("batch") or {}
        wanted = _id(record_id, "record_id")
        binding = next((dict(item) for item in batch.get("records") or [] if item.get("record_id") == wanted), None)
        if binding is None:
            raise IntakeWorkbenchError("metadata_review_source_not_in_batch", 404)
        return binding
