"""Encrypted, local-only matter-intake records for the shipped workbench.

The intake is deliberately a review record, not a classifier or decision maker.
It keeps uncertainty, disputes, and source references intact and never produces a
legal conclusion or an outcome recommendation.
"""

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

from legal.security.durable_io import DurableIOError, atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import StrictJSONError, strict_json_load_path


class IntakeWorkbenchError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


_SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_ANSWER_STATES = frozenset({"known", "unknown", "disputed", "not_applicable", "needs_reviewer"})
_POSTURES = frozenset(
    {
        "pre_filing",
        "initial_complaint",
        "service_pending",
        "temporary_order_stage",
        "discovery_disclosure",
        "mediation",
        "hearing_scheduled",
        "final_order_entered",
        "post_judgment",
        "enforcement",
        "findings_or_reconsideration",
        "appeal",
        "remand",
        "unknown",
    }
)
_MATTER_TYPES = frozenset(
    {
        "divorce",
        "parental_rights_responsibilities",
        "parentage",
        "child_support",
        "post_judgment_modification",
        "enforcement_or_alleged_noncompliance",
        "protection_from_abuse_overlap",
        "guardianship_or_third_party_care",
        "interstate_uccjea",
        "appeal_or_record_review",
        "form_completion",
        "research_only",
        "unknown_other",
    }
)
_MAX_TEXT = 8_000
_MAX_COLLECTION = 250


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_id(value: Any, label: str = "identifier") -> str:
    text = str(value or "").strip().casefold()
    if not _SAFE_ID.fullmatch(text):
        raise IntakeWorkbenchError(f"{label}_invalid")
    return text


def _bounded_text(value: Any, *, limit: int = _MAX_TEXT) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return text


def _safe_list(value: Any, *, limit: int = _MAX_COLLECTION) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise IntakeWorkbenchError("collection_invalid_or_too_large")
    return deepcopy(value)


def _safe_record_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntakeWorkbenchError("record_reference_invalid")
    record_id = _safe_id(value.get("record_id"), "record_id")
    result: dict[str, Any] = {"record_id": record_id}
    for field in ("source_hash", "page", "span_start", "span_end", "label"):
        candidate = value.get(field)
        if candidate not in (None, ""):
            if field in {"page", "span_start", "span_end"}:
                try:
                    number = int(candidate)
                except (TypeError, ValueError) as exc:
                    raise IntakeWorkbenchError("record_reference_invalid") from exc
                if number < 0:
                    raise IntakeWorkbenchError("record_reference_invalid")
                result[field] = number
            else:
                result[field] = _bounded_text(candidate, limit=256)
    return result


def _source_refs(value: Any) -> list[dict[str, Any]]:
    return [_safe_record_ref(item) for item in _safe_list(value)]


def _public_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # History is already scrubbed of raw paths and only contains user-entered
    # fields. Keep it explicit so a caller never receives storage internals.
    return deepcopy(history)


class MatterIntakeStore:
    """Versioned encrypted intake store scoped to one selected local matter."""

    schema = "maine_family_law_llm.matter_intake.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        if not self.case_root.is_dir() or self.case_root.is_symlink():
            raise IntakeWorkbenchError("active_matter_unavailable", 409)
        self.root = self.case_root / "20_MATTER_INTAKE"
        if self.root.exists() and self.root.is_symlink():
            raise IntakeWorkbenchError("intake_store_symlink_refused", 409)
        key = (
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        try:
            self.encryptor = LocalEnvelopeEncryptor(key)
        except ValueError as exc:
            raise IntakeWorkbenchError("intake_encryption_unavailable", 409) from exc
        self.scope_id = hashlib.sha256(str(self.case_root).encode("utf-8")).hexdigest()[:24]

    def _matter_dir(self, matter_id: str) -> Path:
        return self.root / _safe_id(matter_id, "matter_id")

    def _record_path(self, matter_id: str) -> Path:
        return self._matter_dir(matter_id) / "intake.json.enc"

    def _lock_path(self, matter_id: str) -> Path:
        return self._matter_dir(matter_id) / ".intake.lock"

    def _read(self, matter_id: str) -> dict[str, Any]:
        path = self._record_path(matter_id)
        if not path.exists():
            raise IntakeWorkbenchError("matter_intake_not_found", 404)
        try:
            envelope = strict_json_load_path(path, max_bytes=4 * 1024 * 1024, require_object=True)
            record = self.encryptor.decrypt_json(envelope)
        except (StrictJSONError, DurableIOError, ValueError, OSError) as exc:
            raise IntakeWorkbenchError("matter_intake_unavailable", 409) from exc
        if record.get("schema") != self.schema or record.get("matter_id") != matter_id:
            raise IntakeWorkbenchError("matter_intake_integrity_invalid", 409)
        if record.get("scope_id") != self.scope_id:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        self._verify_history(record)
        return record

    def _write(self, matter_id: str, record: dict[str, Any]) -> None:
        path = self._record_path(matter_id)
        payload = self.encryptor.encrypt_json(record)
        try:
            atomic_write_bytes(path, _canonical(payload), mode=0o600)
        except DurableIOError as exc:
            raise IntakeWorkbenchError("matter_intake_write_failed", 409) from exc

    def _verify_history(self, record: dict[str, Any]) -> None:
        previous = ""
        for event in record.get("history", []):
            copy = dict(event)
            event_hash = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash", "") != previous or event_hash != _digest(copy):
                raise IntakeWorkbenchError("intake_history_integrity_invalid", 409)
            previous = event_hash

    def _event(self, record: dict[str, Any], *, action: str, changed_fields: list[str]) -> None:
        history = record.setdefault("history", [])
        previous = str(history[-1].get("event_hash") or "") if history else ""
        event = {
            "event_id": f"event_{uuid.uuid4().hex}",
            "at": _now(),
            "action": action,
            "changed_fields": sorted(set(changed_fields)),
            "previous_event_hash": previous,
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        history.append(event)
        record["updated_at"] = event["at"]
        record["revision"] = int(record.get("revision", 0)) + 1

    def _new_record(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        matter_types = [
            item
            for item in _safe_list(payload.get("matter_type_candidates"))
            if item in _MATTER_TYPES
        ]
        if len(matter_types) != len(set(matter_types)):
            raise IntakeWorkbenchError("matter_type_candidates_invalid")
        record: dict[str, Any] = {
            "schema": self.schema,
            "matter_id": matter_id,
            "scope_id": self.scope_id,
            "created_at": now,
            "updated_at": now,
            "revision": 0,
            "status": "in_progress",
            "review_required": True,
            "not_legal_advice": True,
            "jurisdiction_package": {
                "id": _bounded_text(payload.get("jurisdiction_package") or "maine", limit=128),
                "version": _bounded_text(
                    payload.get("jurisdiction_version") or "unknown", limit=128
                ),
            },
            "matter_type_candidates": matter_types or ["unknown_other"],
            "court": {
                "court": _bounded_text(payload.get("court"), limit=256),
                "county": _bounded_text(payload.get("county"), limit=128),
                "docket_safe_identifier": _bounded_text(
                    payload.get("docket_safe_identifier"), limit=128
                ),
            },
            "participants": [],
            "children": [],
            "procedural_posture": {
                "state": "unknown",
                "source_refs": [],
                "entry_status": "unknown",
            },
            "operative_order_candidates": [],
            "hearing_and_filing_dates": [],
            "requested_workflow": _bounded_text(payload.get("requested_workflow"), limit=1_000),
            "record_scope": {
                "selected_record_roots": [],
                "included_records": [],
                "excluded_records": [],
                "privacy_indicators": [],
            },
            "external_sharing_policy": "local_only_no_external_sharing",
            "retention_policy": "review_required",
            "backup_policy": "review_required",
            "human_review_assignment": {"status": "needs_reviewer", "reviewer_safe_id": ""},
            "questionnaire": {},
            "issue_tree": [],
            "history": [],
        }
        self._event(
            record,
            action="created",
            changed_fields=["matter_id", "matter_type_candidates", "jurisdiction_package"],
        )
        return record

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        matter_id = _safe_id(
            payload.get("matter_id") or f"matter_{uuid.uuid4().hex[:16]}", "matter_id"
        )
        matter_dir = self._matter_dir(matter_id)
        if matter_dir.exists() and matter_dir.is_symlink():
            raise IntakeWorkbenchError("intake_store_symlink_refused", 409)
        with exclusive_file_lock(self._lock_path(matter_id)):
            if self._record_path(matter_id).exists():
                raise IntakeWorkbenchError("matter_intake_exists", 409)
            record = self._new_record(matter_id, payload)
            self._write(matter_id, record)
        return self.public(record)

    def get(self, matter_id: str) -> dict[str, Any]:
        return self.public(self._read(_safe_id(matter_id, "matter_id")))

    def update(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        matter_id = _safe_id(matter_id, "matter_id")
        allowed = {
            "matter_type_candidates",
            "court",
            "participants",
            "children",
            "requested_workflow",
            "external_sharing_policy",
            "retention_policy",
            "backup_policy",
            "human_review_assignment",
            "record_scope",
            "operative_order_candidates",
            "hearing_and_filing_dates",
        }
        unexpected = set(payload) - allowed
        if unexpected:
            raise IntakeWorkbenchError("intake_field_not_editable")
        with exclusive_file_lock(self._lock_path(matter_id)):
            record = self._read(matter_id)
            changed: list[str] = []
            if "matter_type_candidates" in payload:
                values = _safe_list(payload["matter_type_candidates"])
                if not values or any(item not in _MATTER_TYPES for item in values):
                    raise IntakeWorkbenchError("matter_type_candidates_invalid")
                record["matter_type_candidates"] = values
                changed.append("matter_type_candidates")
            if "court" in payload:
                court = payload["court"]
                if not isinstance(court, dict):
                    raise IntakeWorkbenchError("court_invalid")
                record["court"] = {
                    key: _bounded_text(court.get(key), limit=256)
                    for key in ("court", "county", "docket_safe_identifier")
                }
                changed.append("court")
            for collection in ("participants", "children"):
                if collection in payload:
                    normalized = []
                    for item in _safe_list(payload[collection]):
                        if not isinstance(item, dict):
                            raise IntakeWorkbenchError(f"{collection}_invalid")
                        normalized.append(
                            {
                                "safe_id": _safe_id(item.get("safe_id"), f"{collection}_safe_id"),
                                "role": _bounded_text(item.get("role"), limit=128),
                                "relationship_status": str(
                                    item.get("relationship_status") or "needs_reviewer"
                                ),
                                "source_refs": _source_refs(item.get("source_refs")),
                            }
                        )
                    record[collection] = normalized
                    changed.append(collection)
            for name in (
                "requested_workflow",
                "external_sharing_policy",
                "retention_policy",
                "backup_policy",
            ):
                if name in payload:
                    record[name] = _bounded_text(payload[name], limit=1_000)
                    changed.append(name)
            if "human_review_assignment" in payload:
                item = payload["human_review_assignment"]
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("human_review_assignment_invalid")
                record["human_review_assignment"] = {
                    "status": str(item.get("status") or "needs_reviewer"),
                    "reviewer_safe_id": _safe_id(item["reviewer_safe_id"], "reviewer_safe_id")
                    if item.get("reviewer_safe_id")
                    else "",
                }
                changed.append("human_review_assignment")
            if "record_scope" in payload:
                item = payload["record_scope"]
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("record_scope_invalid")
                privacy = [str(value) for value in _safe_list(item.get("privacy_indicators"))]
                allowed_privacy = {
                    "sealed",
                    "juvenile",
                    "medical",
                    "school",
                    "financial",
                    "privilege",
                    "confidential",
                }
                if any(value not in allowed_privacy for value in privacy):
                    raise IntakeWorkbenchError("privacy_indicator_invalid")
                record["record_scope"] = {
                    "selected_record_roots": [
                        _bounded_text(value, limit=256)
                        for value in _safe_list(item.get("selected_record_roots"))
                    ],
                    "included_records": _source_refs(item.get("included_records")),
                    "excluded_records": _source_refs(item.get("excluded_records")),
                    "privacy_indicators": sorted(set(privacy)),
                }
                changed.append("record_scope")
            if "operative_order_candidates" in payload:
                record["operative_order_candidates"] = _source_refs(
                    payload["operative_order_candidates"]
                )
                changed.append("operative_order_candidates")
            if "hearing_and_filing_dates" in payload:
                record["hearing_and_filing_dates"] = _safe_list(payload["hearing_and_filing_dates"])
                changed.append("hearing_and_filing_dates")
            self._event(record, action="corrected", changed_fields=changed)
            self._write(matter_id, record)
        return self.public(record)

    def classify(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        matter_id = _safe_id(matter_id, "matter_id")
        answers = payload.get("answers")
        if not isinstance(answers, dict) or len(answers) > _MAX_COLLECTION:
            raise IntakeWorkbenchError("questionnaire_invalid")
        normalized: dict[str, Any] = {}
        for question_id, answer in answers.items():
            qid = _safe_id(question_id, "question_id")
            if not isinstance(answer, dict) or answer.get("state") not in _ANSWER_STATES:
                raise IntakeWorkbenchError("questionnaire_answer_invalid")
            normalized[qid] = {
                "state": answer["state"],
                "value": _bounded_text(answer.get("value"), limit=2_000),
                "source_refs": _source_refs(answer.get("source_refs")),
                "review_required": answer["state"] in {"unknown", "disputed", "needs_reviewer"},
            }
        with exclusive_file_lock(self._lock_path(matter_id)):
            record = self._read(matter_id)
            record["questionnaire"].update(normalized)
            self._event(
                record,
                action="questionnaire_updated",
                changed_fields=[f"questionnaire.{key}" for key in normalized],
            )
            self._write(matter_id, record)
        return self.public(record)

    def posture(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload.get("state") or "unknown")
        if state not in _POSTURES:
            raise IntakeWorkbenchError("procedural_posture_invalid")
        posture = {
            "state": state,
            "entry_status": str(
                payload.get("entry_status") or ("unknown" if state == "unknown" else "known")
            ),
            "source_refs": _source_refs(payload.get("source_refs")),
            "review_required": True,
        }
        matter_id = _safe_id(matter_id, "matter_id")
        with exclusive_file_lock(self._lock_path(matter_id)):
            record = self._read(matter_id)
            record["procedural_posture"] = posture
            self._event(record, action="posture_updated", changed_fields=["procedural_posture"])
            self._write(matter_id, record)
        return self.public(record)

    def issue_tree(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        nodes = _safe_list(payload.get("issues"))
        normalized = []
        prohibited = re.compile(
            r"\b(wins?|unfit|committed abuse|violated an order|should receive|best parent)\b", re.I
        )
        for item in nodes:
            if not isinstance(item, dict):
                raise IntakeWorkbenchError("issue_node_invalid")
            label = _bounded_text(item.get("issue_label"), limit=256)
            concern = _bounded_text(item.get("user_stated_concern"), limit=2_000)
            if prohibited.search(label) or prohibited.search(concern):
                raise IntakeWorkbenchError("outcome_or_fitness_language_refused")
            normalized.append(
                {
                    "issue_id": _safe_id(item.get("issue_id"), "issue_id"),
                    "issue_label": label,
                    "posture": str(item.get("posture") or "unknown"),
                    "user_stated_concern": concern,
                    "factual_claims": _safe_list(item.get("factual_claims")),
                    "supporting_records": _source_refs(item.get("supporting_records")),
                    "contradicting_records": _source_refs(item.get("contradicting_records")),
                    "applicable_authority_candidates": _safe_list(
                        item.get("applicable_authority_candidates")
                    ),
                    "missing_facts": [
                        _bounded_text(value, limit=1_000)
                        for value in _safe_list(item.get("missing_facts"))
                    ],
                    "missing_records": [
                        _bounded_text(value, limit=1_000)
                        for value in _safe_list(item.get("missing_records"))
                    ],
                    "forms": [
                        _bounded_text(value, limit=256) for value in _safe_list(item.get("forms"))
                    ],
                    "deadlines_requiring_review": _safe_list(
                        item.get("deadlines_requiring_review")
                    ),
                    "reviewer_notes": _bounded_text(item.get("reviewer_notes"), limit=2_000),
                    "status": str(item.get("status") or "review_required"),
                    "history": [],
                }
            )
        matter_id = _safe_id(matter_id, "matter_id")
        with exclusive_file_lock(self._lock_path(matter_id)):
            record = self._read(matter_id)
            record["issue_tree"] = normalized
            self._event(record, action="issue_tree_updated", changed_fields=["issue_tree"])
            self._write(matter_id, record)
        return self.public(record)

    def coverage(self, matter_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        record = self._read(_safe_id(matter_id, "matter_id"))
        inventory = []
        for row in records[:2_000]:
            record_id = str(row.get("evidence_id") or "").casefold()
            if not _SAFE_ID.fullmatch(record_id):
                continue
            metadata = dict(row.get("parser_metadata") or {})
            inventory.append(
                {
                    "record_id": record_id,
                    "title": _bounded_text(row.get("title") or "Indexed record", limit=256),
                    "source_type": _bounded_text(row.get("source_type") or "unknown", limit=128),
                    "source_hash": _bounded_text(row.get("source_hash") or "", limit=128),
                    "parser_status": _bounded_text(
                        row.get("parser_status") or "unknown", limit=128
                    ),
                    "record_type": _bounded_text(
                        metadata.get("document_kind") or row.get("source_type") or "unknown",
                        limit=128,
                    ),
                }
            )
        included = {ref["record_id"] for ref in record["record_scope"].get("included_records", [])}
        excluded = {ref["record_id"] for ref in record["record_scope"].get("excluded_records", [])}
        known = {row["record_id"] for row in inventory}
        missing = []
        posture = record["procedural_posture"]["state"]
        types = {row["source_type"] for row in inventory}
        if posture in {
            "final_order_entered",
            "post_judgment",
            "enforcement",
            "appeal",
            "remand",
        } and not any("order" in value for value in types):
            missing.append("operative_order_missing")
        if posture in {"hearing_scheduled", "appeal", "remand"} and not any(
            "transcript" in value for value in types
        ):
            missing.append("transcript_missing")
        if any(
            value
            in {"sealed", "juvenile", "medical", "school", "financial", "privilege", "confidential"}
            for value in record["record_scope"].get("privacy_indicators", [])
        ):
            privacy_warning = True
        else:
            privacy_warning = any(
                any(
                    word in row["source_type"].casefold()
                    for word in ("medical", "school", "financial", "juvenile")
                )
                for row in inventory
            )
        return {
            "status": "review_required",
            "review_required": True,
            "matter_id": record["matter_id"],
            "records_included": sorted(included & known),
            "records_excluded": sorted(excluded & known),
            "unclassified_record_ids": sorted(known - included - excluded),
            "inventory": inventory,
            "date_span_represented": "unknown_review_required",
            "date_gaps": ["not_calculated_without_review"],
            "duplicate_groups": [],
            "missing_attachments": [],
            "missing_record_checklist": missing,
            "privacy_warning": privacy_warning,
            "completeness_percentage": None,
            "limitations": [
                "Coverage is an inventory and does not establish completeness, authenticity, "
                "relevance, or legal sufficiency."
            ],
        }

    def complete(self, matter_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        matter_id = _safe_id(matter_id, "matter_id")
        with exclusive_file_lock(self._lock_path(matter_id)):
            record = self._read(matter_id)
            coverage = self.coverage(matter_id, records)
            record["status"] = "review_required"
            record["completion"] = {
                "completed_at": _now(),
                "missing_record_checklist": coverage["missing_record_checklist"],
                "privacy_warning": coverage["privacy_warning"],
                "authority_research_queue": [
                    node["issue_id"]
                    for node in record["issue_tree"]
                    if node.get("applicable_authority_candidates")
                ],
                "reviewer_assignment_checklist": [
                    "confirm matter scope",
                    "review unknown and disputed answers",
                    "confirm source references",
                    "review privacy and sharing policy",
                ],
                "review_required": True,
            }
            self._event(
                record, action="completion_prepared", changed_fields=["completion", "status"]
            )
            self._write(matter_id, record)
        return self.public(record)

    def receipt(self, matter_id: str) -> dict[str, Any]:
        record = self._read(_safe_id(matter_id, "matter_id"))
        public = self.public(record)
        receipt = {
            "schema": "maine_family_law_llm.intake_receipt.v1",
            "matter_id": record["matter_id"],
            "revision": record["revision"],
            "status": record["status"],
            "review_required": True,
            "not_legal_advice": True,
            "history_tip_hash": str(record["history"][-1].get("event_hash") or ""),
            "intake_hash": _digest(public),
            "created_at": record["created_at"],
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _digest(receipt)
        return receipt

    def public(self, record: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(record)
        result.pop("scope_id", None)
        result["history"] = _public_history(result.get("history") or [])
        result["storage"] = {
            "local_only": True,
            "encrypted": True,
            "external_sharing_default": "disabled",
            "raw_paths_exposed": False,
        }
        return result
