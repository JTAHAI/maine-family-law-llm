"""Encrypted local reconciliation of user-provided docket and matter records."""

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

_SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_STATUSES = frozenset(
    {
        "exact_match",
        "likely_match",
        "docket_only",
        "local_only",
        "missing_attachment",
        "duplicate",
        "changed_copy",
        "rejected_filing",
        "sealed_confidential",
        "unavailable",
        "ambiguous",
        "reviewer_required",
    }
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _id(value: Any, label: str) -> str:
    text = str(value or "").strip().casefold()
    if not _SAFE_ID.fullmatch(text):
        raise IntakeWorkbenchError(f"{label}_invalid")
    return text


def _text(value: Any, limit: int = 4_000) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return text


class DocketReconciliationStore:
    schema = "maine_family_law_llm.docket_reconciliation.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "23_DOCKET_RECONCILIATION"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("docket_store_unavailable", 409)
        key = (
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "docket.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".docket.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "entries": [],
                "local_records": [],
                "history": [],
                "revision": 0,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("docket_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, action: str, ids: list[str], callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = callback(value)
            prior = value["history"][-1]["event_hash"] if value["history"] else ""
            event = {
                "event_id": f"docket_event_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": ids,
                "previous_event_hash": prior,
                "review_required": True,
            }
            event["event_hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def public(self, value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "court_portal_access": False,
                "official_record_completeness": "not_determined",
            }
        )
        return result

    def inventory(self) -> dict[str, Any]:
        return self.public(self._load())

    def import_entries(self, payload: dict[str, Any]) -> dict[str, Any]:
        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries or len(entries) > 1_000:
            raise IntakeWorkbenchError("docket_entries_invalid")

        def callback(value):
            known = {row["entry_id"] for row in value["entries"]}
            for item in entries:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("docket_entry_invalid")
                entry_id = _id(item.get("entry_id"), "entry_id")
                if entry_id in known:
                    raise IntakeWorkbenchError("duplicate_docket_entry", 409)
                source = item.get("source_ref") or {}
                value["entries"].append(
                    {
                        "entry_id": entry_id,
                        "docket_safe_id": _text(item.get("docket_safe_id"), 128),
                        "sequence": _text(item.get("sequence"), 64),
                        "filed_or_entered_date": _text(item.get("filed_or_entered_date"), 64),
                        "description": _text(item.get("description"), 2_000),
                        "document_type_candidate": _text(item.get("document_type_candidate"), 128),
                        "filer_role": _text(item.get("filer_role"), 128),
                        "status": str(item.get("status") or "reviewer_required"),
                        "source_ref": {
                            "record_id": _id(source.get("record_id"), "record_id"),
                            "source_hash": _text(source.get("source_hash"), 128),
                            "page": source.get("page"),
                        },
                        "referenced_attachment": _text(item.get("referenced_attachment"), 256),
                        "local_document_match": None,
                        "confidence": 0.0,
                        "reviewer_status": "review_required",
                    }
                )
                known.add(entry_id)
            return self.public(value)

        return self._mutate(
            "docket_imported",
            [_id(row.get("entry_id"), "entry_id") for row in entries if isinstance(row, dict)],
            callback,
        )

    def add_local_records(self, payload: dict[str, Any]) -> dict[str, Any]:
        records = payload.get("records")
        if not isinstance(records, list) or len(records) > 1_000:
            raise IntakeWorkbenchError("local_records_invalid")

        def callback(value):
            known = {row["record_id"] for row in value["local_records"]}
            for item in records:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("local_record_invalid")
                record_id = _id(item.get("record_id"), "record_id")
                if record_id in known:
                    raise IntakeWorkbenchError("duplicate_local_record", 409)
                value["local_records"].append(
                    {
                        "record_id": record_id,
                        "title": _text(item.get("title"), 512),
                        "source_hash": _text(item.get("source_hash"), 128),
                        "date": _text(item.get("date"), 64),
                        "page_count": item.get("page_count"),
                        "sealed_confidential": bool(item.get("sealed_confidential")),
                        "status": "local_only",
                    }
                )
                known.add(record_id)
            return self.public(value)

        return self._mutate(
            "local_records_added",
            [_id(row.get("record_id"), "record_id") for row in records if isinstance(row, dict)],
            callback,
        )

    def reconcile(self) -> dict[str, Any]:
        value = self._load()
        records = value["local_records"]
        decisions = []
        for entry in value["entries"]:
            exact = next(
                (
                    r
                    for r in records
                    if r["source_hash"] and r["source_hash"] == entry["source_ref"]["source_hash"]
                ),
                None,
            )
            likely = next(
                (
                    r
                    for r in records
                    if r["title"].casefold()
                    and r["title"].casefold() in entry["description"].casefold()
                ),
                None,
            )
            match = exact or likely
            status = "exact_match" if exact else ("likely_match" if likely else "docket_only")
            if entry["status"] in _STATUSES - {"reviewer_required"}:
                status = entry["status"]
            decisions.append(
                {
                    "entry_id": entry["entry_id"],
                    "record_id": match["record_id"] if match else "",
                    "status": status,
                    "confidence": 1.0 if exact else (0.6 if likely else 0.0),
                    "review_required": True,
                }
            )
        matched = {row["record_id"] for row in decisions if row["record_id"]}
        local_only = [r["record_id"] for r in records if r["record_id"] not in matched]
        return {
            "status": "review_required",
            "review_required": True,
            "decisions": decisions,
            "local_only_record_ids": local_only,
            "missing_attachments": [
                e["entry_id"]
                for e in value["entries"]
                if e["referenced_attachment"]
                and not any(
                    e["referenced_attachment"].casefold() in r["title"].casefold() for r in records
                )
            ],
            "sealed_warning": any(r["sealed_confidential"] for r in records),
            "official_record_completeness": "not_determined",
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        result = {
            "revision": value["revision"],
            "entries_hash": _hash(value["entries"]),
            "local_records_hash": _hash(value["local_records"]),
            "review_required": True,
            "official_record_completeness": "not_determined",
            "issued_at": _now(),
        }
        result["receipt_hash"] = _hash(result)
        return result
