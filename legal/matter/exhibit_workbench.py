"""Encrypted, review-first exhibit labels, derivative numbering, and provenance."""

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

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_LABEL = re.compile(r"(?:Exhibit|Attachment|Appendix) [A-Za-z0-9-]{1,32}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _id(value: Any, label: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{label}_invalid")
    return result


def _text(value: Any, limit: int = 8_000) -> str:
    result = str(value or "").strip()
    if len(result) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return result


class ExhibitWorkbenchStore:
    """Stores plans and manifests only; original source files are never modified."""

    schema = "maine_family_law_llm.exhibit_workbench.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "25_EXHIBIT_WORKBENCH"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("exhibit_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "exhibits.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".exhibits.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "candidates": [],
                "numberings": [],
                "binders": [],
                "ledger": [],
                "revision": 0,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("exhibit_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, action: str, identifiers: list[str], callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = callback(value)
            prior = value["ledger"][-1]["event_hash"] if value["ledger"] else ""
            event = {
                "event_id": f"custody_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "identifiers": identifiers,
                "previous_event_hash": prior,
                "review_required": True,
            }
            event["event_hash"] = _hash(event)
            value["ledger"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "originals_immutable": True,
                "authenticity": "not_determined",
                "admissibility": "not_determined",
            }
        )
        return result

    def inventory(self) -> dict[str, Any]:
        return self._public(self._load())

    def add_candidates(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("candidates")
        if not isinstance(rows, list) or not rows or len(rows) > 1_000:
            raise IntakeWorkbenchError("exhibit_candidates_invalid")

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            known = {row["exhibit_id"] for row in value["candidates"]}
            for row in rows:
                if not isinstance(row, dict):
                    raise IntakeWorkbenchError("exhibit_candidate_invalid")
                exhibit_id, record_id = (
                    _id(row.get("exhibit_id"), "exhibit_id"),
                    _id(row.get("original_record_id"), "original_record_id"),
                )
                if exhibit_id in known:
                    raise IntakeWorkbenchError("duplicate_exhibit_id", 409)
                source_hash = _text(row.get("original_hash"), 128)
                if len(source_hash) != 64:
                    raise IntakeWorkbenchError("original_hash_required")
                proposed_label = _text(row.get("proposed_label"), 64)
                if proposed_label and not _LABEL.fullmatch(proposed_label):
                    raise IntakeWorkbenchError("label_invalid")
                value["candidates"].append(
                    {
                        "exhibit_id": exhibit_id,
                        "original_record_id": record_id,
                        "original_hash": source_hash,
                        "proposed_label": proposed_label,
                        "approved_label": "",
                        "description": _text(row.get("description"), 2_000),
                        "date": _text(row.get("date"), 64),
                        "page_count": int(row.get("page_count") or 0),
                        "links": [_id(item, "linked_id") for item in row.get("links", [])],
                        "confidentiality": _text(row.get("confidentiality"), 128),
                        "redaction_state": _text(row.get("redaction_state") or "not_reviewed", 128),
                        "duplicate_group": _text(row.get("duplicate_group"), 128),
                        "version": _text(row.get("version") or "original_candidate", 128),
                        "inclusion_status": "review_required",
                        "reviewer_history": [],
                    }
                )
                known.add(exhibit_id)
            return self._public(value)

        return self._mutate(
            "candidate_import",
            [_id(row.get("exhibit_id"), "exhibit_id") for row in rows if isinstance(row, dict)],
            callback,
        )

    def review_label(self, payload: dict[str, Any]) -> dict[str, Any]:
        exhibit_id = _id(payload.get("exhibit_id"), "exhibit_id")
        label = _text(payload.get("approved_label"), 64)
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        if not _LABEL.fullmatch(label):
            raise IntakeWorkbenchError("label_invalid")

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            row = next(
                (item for item in value["candidates"] if item["exhibit_id"] == exhibit_id), None
            )
            if row is None:
                raise IntakeWorkbenchError("exhibit_not_found", 404)
            if any(
                item["approved_label"] == label
                for item in value["candidates"]
                if item["exhibit_id"] != exhibit_id
            ):
                raise IntakeWorkbenchError("duplicate_approved_label", 409)
            row["approved_label"] = label
            row["reviewer_history"].append(
                {
                    "at": _now(),
                    "reviewer_safe_id": reviewer,
                    "action": "label_approved",
                    "review_required": True,
                }
            )
            return self._public(value)

        return self._mutate("label_review", [exhibit_id], callback)

    def create_numbering(self, payload: dict[str, Any]) -> dict[str, Any]:
        exhibit_id = _id(payload.get("exhibit_id"), "exhibit_id")
        prefix = _text(payload.get("prefix"), 24)
        start = int(payload.get("start") or 0)
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        if not prefix or start < 1:
            raise IntakeWorkbenchError("numbering_settings_invalid")

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            candidate = next(
                (item for item in value["candidates"] if item["exhibit_id"] == exhibit_id), None
            )
            if candidate is None or candidate["page_count"] < 1:
                raise IntakeWorkbenchError("numbering_candidate_invalid")
            end = start + candidate["page_count"] - 1
            for item in value["numberings"]:
                if item["prefix"] == prefix and not (end < item["start"] or start > item["end"]):
                    raise IntakeWorkbenchError("conflicting_number_range", 409)
            derivative = {
                "derivative_id": f"derivative_{uuid.uuid4().hex}",
                "exhibit_id": exhibit_id,
                "numbering_scheme": "control_number",
                "prefix": prefix,
                "start": start,
                "end": end,
                "page_mapping": [
                    {"source_page": page, "control_number": f"{prefix}{start + page - 1}"}
                    for page in range(1, candidate["page_count"] + 1)
                ],
                "source_hash": candidate["original_hash"],
                "settings": {"watermark": "REVIEW REQUIRED", "original_modified": False},
                "reviewer_safe_id": reviewer,
                "review_required": True,
            }
            derivative["derivative_hash"] = _hash(derivative)
            value["numberings"].append(derivative)
            return deepcopy(derivative)

        return self._mutate("numbering_derivative_created", [exhibit_id], callback)

    def create_binder(self, payload: dict[str, Any]) -> dict[str, Any]:
        binder_id = _id(payload.get("binder_id"), "binder_id")
        selected = [_id(item, "exhibit_id") for item in payload.get("exhibit_ids", [])]
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        if not selected or len(selected) > 250 or len(set(selected)) != len(selected):
            raise IntakeWorkbenchError("binder_selection_invalid")

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["binder_id"] == binder_id for item in value["binders"]):
                raise IntakeWorkbenchError("duplicate_binder_id", 409)
            records = []
            for exhibit_id in selected:
                candidate = next(
                    (item for item in value["candidates"] if item["exhibit_id"] == exhibit_id), None
                )
                if candidate is None:
                    raise IntakeWorkbenchError("selected_exhibit_missing", 404)
                if not candidate["approved_label"]:
                    raise IntakeWorkbenchError("approved_label_required")
                if (
                    candidate["redaction_state"] in {"needs_review", "not_reviewed"}
                    and candidate["confidentiality"]
                ):
                    raise IntakeWorkbenchError("privacy_review_required")
                records.append(candidate)
            page = 2
            mapping = []
            for record in records:
                first, last = page, page + max(1, record["page_count"]) - 1
                mapping.append(
                    {
                        "exhibit_id": record["exhibit_id"],
                        "label": record["approved_label"],
                        "binder_start_page": first,
                        "binder_end_page": last,
                        "original_hash": record["original_hash"],
                    }
                )
                page = last + 2
            binder = {
                "binder_id": binder_id,
                "selected_exhibit_ids": selected,
                "cover": "REVIEW REQUIRED — local derivative binder",
                "has_index": True,
                "has_separator_pages": True,
                "includes_originals_by_default": False,
                "page_mapping": mapping,
                "missing_item_warnings": [],
                "reviewer_safe_id": reviewer,
                "review_required": True,
                "created_at": _now(),
            }
            binder["hash_manifest"] = _hash(
                {
                    "page_mapping": mapping,
                    "candidate_hashes": [record["original_hash"] for record in records],
                }
            )
            binder["binder_hash"] = _hash(binder)
            value["binders"].append(binder)
            return deepcopy(binder)

        return self._mutate("binder_derivative_created", [binder_id, *selected], callback)

    def manifest(self, binder_id: str) -> dict[str, Any]:
        binder = next(
            (
                item
                for item in self._load()["binders"]
                if item["binder_id"] == _id(binder_id, "binder_id")
            ),
            None,
        )
        if binder is None:
            raise IntakeWorkbenchError("binder_not_found", 404)
        return {
            "status": "review_required",
            "review_required": True,
            "binder_id": binder["binder_id"],
            "page_mapping": binder["page_mapping"],
            "hash_manifest": binder["hash_manifest"],
            "authenticity": "not_determined",
            "admissibility": "not_determined",
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "candidates_hash": _hash(value["candidates"]),
            "numberings_hash": _hash(value["numberings"]),
            "binders_hash": _hash(value["binders"]),
            "ledger_hash": _hash(value["ledger"]),
            "review_required": True,
            "originals_immutable": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
