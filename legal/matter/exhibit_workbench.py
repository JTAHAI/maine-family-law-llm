"""Encrypted, review-first exhibit labels, derivative numbering, and provenance."""

from __future__ import annotations

import hashlib
import hmac
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
_CUSTODY_EVENT_TYPES = {
    "collection",
    "transfer",
    "transformation",
    "hashing",
    "review",
    "export",
}


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
                "admission_checklists": [],
                "custody_events": [],
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
        # Keep existing encrypted exhibit stores forward compatible.  A review
        # checklist is derived work product; it must not require rewriting an
        # older matter or altering an original exhibit candidate.
        value.setdefault("admission_checklists", [])
        value.setdefault("custody_events", [])
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

    def create_admission_checklist(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create neutral, source-bound review prompts for one exhibit.

        This is deliberately not an admissibility engine.  The four categories
        make it easier for a reviewer to see what still needs attention, while
        leaving every legal and factual conclusion unresolved.
        """
        checklist_id = _id(payload.get("checklist_id"), "checklist_id")
        exhibit_id = _id(payload.get("exhibit_id"), "exhibit_id")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        reviewer_note = _text(payload.get("reviewer_note"), 2_000)

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["checklist_id"] == checklist_id for item in value["admission_checklists"]):
                raise IntakeWorkbenchError("duplicate_admission_checklist_id", 409)
            candidate = next(
                (item for item in value["candidates"] if item["exhibit_id"] == exhibit_id), None
            )
            if candidate is None:
                raise IntakeWorkbenchError("exhibit_not_found", 404)
            source = {
                "record_id": candidate["original_record_id"],
                "source_hash": candidate["original_hash"],
                "description": candidate["description"],
            }
            categories = {
                "foundation_questions": "What source-grounded witness, record, or handling detail should a reviewer examine for foundation?",
                "authenticity_materials": "What source material could a reviewer compare with this exhibit when assessing authenticity?",
                "objection_candidates": "What source-context limitation or potential objection should a reviewer identify and assess?",
                "missing_proof": "What additional source, context, or witness information appears missing for reviewer follow-up?",
            }
            checklist = {
                "checklist_id": checklist_id,
                "exhibit_id": exhibit_id,
                "candidate_source": source,
                "categories": {
                    category: [
                        {
                            "item_id": f"{checklist_id}_{category[:12]}",
                            "review_prompt": prompt,
                            "source_ref": deepcopy(source),
                            "state": "unresolved",
                            "review_required": True,
                        }
                    ]
                    for category, prompt in categories.items()
                },
                "reviewer_safe_id": reviewer,
                "reviewer_note": reviewer_note,
                "created_at": _now(),
                "review_required": True,
                "admissibility": "not_determined",
                "authenticity": "not_determined",
                "foundation": "not_determined",
            }
            checklist["checklist_hash"] = _hash(checklist)
            value["admission_checklists"].append(checklist)
            return deepcopy(checklist)

        return self._mutate("admission_checklist_created", [checklist_id, exhibit_id], callback)

    def admission_checklist(self, checklist_id: str) -> dict[str, Any]:
        result = next(
            (
                item
                for item in self._load()["admission_checklists"]
                if item["checklist_id"] == _id(checklist_id, "checklist_id")
            ),
            None,
        )
        if result is None:
            raise IntakeWorkbenchError("admission_checklist_not_found", 404)
        return {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "checklist": deepcopy(result),
            "admissibility": "not_determined",
            "authenticity": "not_determined",
        }

    def admission_checklist_source(self, checklist_id: str) -> dict[str, Any]:
        """Return only the checklist's exact source reference, never a conclusion."""
        checklist = self.admission_checklist(checklist_id)["checklist"]
        return {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "checklist_id": checklist["checklist_id"],
            "exhibit_id": checklist["exhibit_id"],
            "source": deepcopy(checklist["candidate_source"]),
            "source_hash": checklist["candidate_source"]["source_hash"],
            "admissibility": "not_determined",
            "authenticity": "not_determined",
        }

    def _custody_receipt(self, event: dict[str, Any]) -> dict[str, Any]:
        """Create a local integrity receipt, not a person or court signature."""
        receipt = {
            "receipt_schema": "maine_family_law_llm.custody_receipt.v1",
            "event_id": event["event_id"],
            "event_hash": event["event_hash"],
            "previous_event_hash": event["previous_event_hash"],
            "source_hash": event["source_hash"],
            "review_required": True,
            "signature_algorithm": "hmac-sha256-local-matter-key",
            "signature_meaning": "local integrity receipt; not a person, witness, notary, court, or authenticity signature",
        }
        signing_key = hashlib.sha256(
            b"maine-family-law-llm/custody-receipt/v1|"
            + self.encryptor.passphrase
            + self.scope.encode("ascii")
        ).digest()
        receipt["signature"] = hmac.new(
            signing_key,
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return receipt

    def _receipt_valid(self, receipt: dict[str, Any]) -> bool:
        signature = str(receipt.get("signature") or "")
        unsigned = deepcopy(receipt)
        unsigned.pop("signature", None)
        signing_key = hashlib.sha256(
            b"maine-family-law-llm/custody-receipt/v1|"
            + self.encryptor.passphrase
            + self.scope.encode("ascii")
        ).digest()
        expected = hmac.new(
            signing_key,
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def record_custody_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record one user-confirmed custody observation for an exhibit source."""
        event_id = _id(payload.get("event_id"), "event_id")
        exhibit_id = _id(payload.get("exhibit_id"), "exhibit_id")
        event_type = _text(payload.get("event_type"), 64).casefold()
        actor = _id(payload.get("actor_safe_id"), "actor_safe_id")
        if event_type not in _CUSTODY_EVENT_TYPES:
            raise IntakeWorkbenchError("custody_event_type_invalid")
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("custody_event_confirmation_required")
        occurred_at_claimed = _text(payload.get("occurred_at_claimed"), 160)
        details = _text(payload.get("details"), 2_000)
        related_artifact_id = _text(payload.get("related_artifact_id"), 128)
        related_hash = _text(payload.get("related_hash"), 128).casefold()
        if related_hash and len(related_hash) != 64:
            raise IntakeWorkbenchError("related_hash_invalid")
        if event_type == "transformation" and not (related_artifact_id or related_hash):
            raise IntakeWorkbenchError("transformation_artifact_required")

        def callback(value: dict[str, Any]) -> dict[str, Any]:
            if any(row["event_id"] == event_id for row in value["custody_events"]):
                raise IntakeWorkbenchError("duplicate_custody_event_id", 409)
            candidate = next(
                (item for item in value["candidates"] if item["exhibit_id"] == exhibit_id), None
            )
            if candidate is None:
                raise IntakeWorkbenchError("exhibit_not_found", 404)
            previous = value["custody_events"][-1]["event_hash"] if value["custody_events"] else ""
            event = {
                "event_id": event_id,
                "event_type": event_type,
                "exhibit_id": exhibit_id,
                "source_record_id": candidate["original_record_id"],
                "source_hash": candidate["original_hash"],
                "actor_safe_id": actor,
                "occurred_at_claimed": occurred_at_claimed,
                "details": details,
                "related_artifact_id": related_artifact_id,
                "related_hash": related_hash,
                "user_confirmed": True,
                "recorded_at": _now(),
                "previous_event_hash": previous,
                "review_required": True,
                "custody_status": "recorded_not_verified",
                "authenticity": "not_determined",
            }
            event["event_hash"] = _hash(event)
            event["receipt"] = self._custody_receipt(event)
            value["custody_events"].append(event)
            return deepcopy(event)

        return self._mutate("custody_event_recorded", [event_id, exhibit_id], callback)

    def custody_event(self, event_id: str) -> dict[str, Any]:
        event = next(
            (
                item
                for item in self._load()["custody_events"]
                if item["event_id"] == _id(event_id, "event_id")
            ),
            None,
        )
        if event is None:
            raise IntakeWorkbenchError("custody_event_not_found", 404)
        return {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "event": deepcopy(event),
            "custody_status": "recorded_not_verified",
            "authenticity": "not_determined",
        }

    def custody_event_source(self, event_id: str) -> dict[str, Any]:
        event = self.custody_event(event_id)["event"]
        return {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "source_hash": event["source_hash"],
            "source": {
                "record_id": event["source_record_id"],
                "source_hash": event["source_hash"],
                "exhibit_id": event["exhibit_id"],
            },
            "authenticity": "not_determined",
        }

    def verify_custody_chain(self) -> dict[str, Any]:
        events = self._load()["custody_events"]
        prior = ""
        checks = []
        for event in events:
            unsigned_event = deepcopy(event)
            receipt = unsigned_event.pop("receipt", {})
            event_hash = unsigned_event.pop("event_hash", "")
            hash_valid = _hash(unsigned_event) == event_hash
            linkage_valid = event.get("previous_event_hash") == prior
            signature_valid = isinstance(receipt, dict) and self._receipt_valid(receipt)
            checks.append(
                {
                    "event_id": event.get("event_id", ""),
                    "hash_valid": hash_valid,
                    "linkage_valid": linkage_valid,
                    "signature_valid": signature_valid,
                    "review_required": True,
                }
            )
            prior = str(event_hash)
        valid = all(
            check["hash_valid"] and check["linkage_valid"] and check["signature_valid"]
            for check in checks
        )
        return {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "event_count": len(checks),
            "integrity_valid": valid,
            "checks": checks,
            "notice": "Integrity verification does not prove collection, custody, authenticity, identity, completeness, or admissibility.",
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "candidates_hash": _hash(value["candidates"]),
            "numberings_hash": _hash(value["numberings"]),
            "binders_hash": _hash(value["binders"]),
            "admission_checklists_hash": _hash(value["admission_checklists"]),
            "custody_events_hash": _hash(value["custody_events"]),
            "ledger_hash": _hash(value["ledger"]),
            "review_required": True,
            "originals_immutable": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
