"""Review-first, source-bound order and obligation workbench.

This module records order candidates and their explicit relationships.  It does
not determine which order governs, whether a party complied, or whether contempt
occurred.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import DurableIOError, atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import StrictJSONError, strict_json_load_path

_SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_ORDER_TYPES = frozenset(
    {
        "order",
        "judgment",
        "stipulation",
        "temporary_order",
        "amended_order",
        "clarification",
        "findings_order",
        "protection_order",
        "appellate_mandate",
        "unknown",
    }
)
_TERM_SUBJECTS = frozenset(
    {
        "parental_rights_responsibilities",
        "residence",
        "contact_schedule",
        "holidays",
        "transportation_exchange",
        "communication",
        "decision_making",
        "child_support",
        "medical_childcare_expenses",
        "insurance",
        "property_debt",
        "restraints",
        "supervision",
        "third_party_conditions",
        "deadlines",
        "document_production",
        "other",
    }
)
_EDGE_TYPES = frozenset(
    {
        "amends",
        "replaces",
        "suspends",
        "clarifies",
        "extends",
        "terminates",
        "remands",
        "reinstates",
        "conflicts_with",
        "references",
        "unknown_relationship",
    }
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _safe_id(value: Any, label: str) -> str:
    result = str(value or "").strip().casefold()
    if not _SAFE_ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{label}_invalid")
    return result


def _text(value: Any, limit: int = 8_000) -> str:
    result = str(value or "").strip()
    if len(result) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return result


def _items(value: Any, limit: int = 500) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise IntakeWorkbenchError("collection_invalid_or_too_large")
    return deepcopy(value)


def _source_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntakeWorkbenchError("source_reference_invalid")
    result = {"record_id": _safe_id(value.get("record_id"), "record_id")}
    for key in ("source_hash", "page", "block_start", "block_end"):
        if value.get(key) not in (None, ""):
            result[key] = (
                int(value[key])
                if key in {"page", "block_start", "block_end"}
                else _text(value[key], 128)
            )
    return result


class OrderIntelligenceStore:
    schema = "maine_family_law_llm.order_intelligence.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        if not self.case_root.is_dir() or self.case_root.is_symlink():
            raise IntakeWorkbenchError("active_matter_unavailable", 409)
        self.root = self.case_root / "21_ORDER_INTELLIGENCE"
        if self.root.exists() and self.root.is_symlink():
            raise IntakeWorkbenchError("order_store_symlink_refused", 409)
        key = (
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.scope_id = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def _path(self) -> Path:
        return self.root / "orders.json.enc"

    @property
    def _lock(self) -> Path:
        return self.root / ".orders.lock"

    def _new(self) -> dict[str, Any]:
        record = {
            "schema": self.schema,
            "scope_id": self.scope_id,
            "created_at": _now(),
            "updated_at": _now(),
            "revision": 0,
            "orders": [],
            "edges": [],
            "review_history": [],
            "review_required": True,
            "not_legal_advice": True,
        }
        self._event(record, "initialized", [])
        return record

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._new()
        try:
            payload = self.encryptor.decrypt_json(
                strict_json_load_path(self._path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except (StrictJSONError, DurableIOError, ValueError, OSError) as exc:
            raise IntakeWorkbenchError("order_store_unavailable", 409) from exc
        if payload.get("schema") != self.schema or payload.get("scope_id") != self.scope_id:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return payload

    def _save(self, record: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(
                self._path,
                json.dumps(self.encryptor.encrypt_json(record), sort_keys=True).encode(),
                mode=0o600,
            )
        except DurableIOError as exc:
            raise IntakeWorkbenchError("order_store_write_failed", 409) from exc

    def _event(self, record: dict[str, Any], action: str, ids: list[str]) -> None:
        prior = (
            str(record["review_history"][-1].get("event_hash") or "")
            if record["review_history"]
            else ""
        )
        event = {
            "event_id": f"order_event_{uuid.uuid4().hex}",
            "at": _now(),
            "action": action,
            "ids": ids,
            "previous_event_hash": prior,
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        record["review_history"].append(event)
        record["updated_at"] = event["at"]
        record["revision"] += 1

    def _mutate(self, operation):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self._lock):
            record = self._load()
            result = operation(record)
            self._save(record)
        return result

    def inventory(self) -> dict[str, Any]:
        return self.public(self._load())

    def add_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_orders = _items(payload.get("orders"))
        if not raw_orders:
            raise IntakeWorkbenchError("orders_required")

        def operation(record: dict[str, Any]) -> dict[str, Any]:
            seen = {item["order_id"] for item in record["orders"]}
            added = []
            for item in raw_orders:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("order_invalid")
                order_id = _safe_id(item.get("order_id"), "order_id")
                if order_id in seen:
                    raise IntakeWorkbenchError("order_id_exists", 409)
                order_type = str(item.get("order_type") or "unknown")
                if order_type not in _ORDER_TYPES:
                    raise IntakeWorkbenchError("order_type_invalid")
                terms = [self._term(term, order_id) for term in _items(item.get("terms"))]
                source = _source_ref(item.get("source_ref"))
                added.append(
                    {
                        "order_id": order_id,
                        "source_ref": source,
                        "caption": _text(item.get("caption"), 512),
                        "docket_safe_id": _text(item.get("docket_safe_id"), 128),
                        "court": _text(item.get("court"), 256),
                        "order_type": order_type,
                        "signed_date": _text(item.get("signed_date"), 64),
                        "entered_date": _text(item.get("entered_date"), 64),
                        "effective_date": _text(item.get("effective_date"), 64),
                        "signature_status": str(item.get("signature_status") or "unknown"),
                        "status_candidate": str(item.get("status_candidate") or "unknown"),
                        "freshness_status": str(item.get("freshness_status") or "unknown"),
                        "reviewer_status": "review_required",
                        "terms": terms,
                        "history": [],
                    }
                )
                seen.add(order_id)
            record["orders"].extend(added)
            self._event(record, "orders_added", [item["order_id"] for item in added])
            return self.public(record)

        return self._mutate(operation)

    def _term(self, item: Any, order_id: str) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise IntakeWorkbenchError("term_invalid")
        subject = str(item.get("subject") or "other")
        if subject not in _TERM_SUBJECTS:
            raise IntakeWorkbenchError("term_subject_invalid")
        term_id = _safe_id(item.get("term_id"), "term_id")
        language = _text(item.get("exact_language"), 20_000)
        if not language:
            raise IntakeWorkbenchError("exact_term_language_required")
        source = _source_ref(item.get("source_ref"))
        return {
            "term_id": term_id,
            "order_id": order_id,
            "subject": subject,
            "exact_language": language,
            "source_ref": source,
            "dates": _items(item.get("dates"), 50),
            "party_safe_labels": [
                _text(value, 128) for value in _items(item.get("party_safe_labels"), 50)
            ],
            "conditions": _text(item.get("conditions"), 2_000),
            "exceptions": _text(item.get("exceptions"), 2_000),
            "parser_warnings": [
                _text(value, 512) for value in _items(item.get("parser_warnings"), 50)
            ],
            "reviewer_status": "review_required",
        }

    def graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_edges = _items(payload.get("edges"))

        def operation(record: dict[str, Any]) -> dict[str, Any]:
            ids = {item["order_id"] for item in record["orders"]}
            added = []
            for item in raw_edges:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("graph_edge_invalid")
                source_id, target_id = (
                    _safe_id(item.get("source_order_id"), "source_order_id"),
                    _safe_id(item.get("target_order_id"), "target_order_id"),
                )
                if source_id not in ids or target_id not in ids or source_id == target_id:
                    raise IntakeWorkbenchError("graph_edge_order_invalid")
                relation = str(item.get("relationship") or "unknown_relationship")
                if relation not in _EDGE_TYPES:
                    raise IntakeWorkbenchError("graph_relationship_invalid")
                language = _text(item.get("exact_language"), 4_000)
                reviewer_created = bool(item.get("reviewer_created"))
                if not language and not reviewer_created:
                    raise IntakeWorkbenchError("edge_language_or_reviewer_required")
                added.append(
                    {
                        "edge_id": f"edge_{uuid.uuid4().hex}",
                        "source_order_id": source_id,
                        "target_order_id": target_id,
                        "relationship": relation,
                        "exact_language": language,
                        "source_ref": _source_ref(item["source_ref"])
                        if item.get("source_ref")
                        else None,
                        "reviewer_created": reviewer_created,
                        "status": "review_required",
                    }
                )
            record["edges"].extend(added)
            self._event(record, "graph_updated", [item["edge_id"] for item in added])
            return self.public(record)

        return self._mutate(operation)

    def terms(self, order_id: str | None = None) -> dict[str, Any]:
        record = self._load()
        orders = (
            record["orders"]
            if not order_id
            else [
                item
                for item in record["orders"]
                if item["order_id"] == _safe_id(order_id, "order_id")
            ]
        )
        if order_id and not orders:
            raise IntakeWorkbenchError("order_not_found", 404)
        return {
            "status": "review_required",
            "review_required": True,
            "terms": [term for order in orders for term in order["terms"]],
            "source_bound": True,
        }

    def compare(self, left_term_id: str, right_term_id: str) -> dict[str, Any]:
        left, right = (
            self._find_term(_safe_id(left_term_id, "term_id")),
            self._find_term(_safe_id(right_term_id, "term_id")),
        )
        a, b = left["exact_language"], right["exact_language"]
        matcher = SequenceMatcher(None, a.split(), b.split())
        operations = [
            {"kind": tag, "left": " ".join(a.split()[i1:i2]), "right": " ".join(b.split()[j1:j2])}
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        ]
        return {
            "status": "review_required",
            "review_required": True,
            "left_term": left,
            "right_term": right,
            "semantic_diff": operations,
            "limitations": [
                "A semantic diff shows text changes; it does not determine legal effect."
            ],
        }

    def _find_term(self, term_id: str) -> dict[str, Any]:
        for order in self._load()["orders"]:
            for term in order["terms"]:
                if term["term_id"] == term_id:
                    return term
        raise IntakeWorkbenchError("term_not_found", 404)

    def review_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        term_id = _safe_id(payload.get("term_id"), "term_id")
        reviewer = (
            _safe_id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
            if payload.get("reviewer_safe_id")
            else ""
        )
        confirmed = bool(payload.get("confirmed"))

        def operation(record: dict[str, Any]) -> dict[str, Any]:
            found = None
            for order in record["orders"]:
                for term in order["terms"]:
                    if term["term_id"] == term_id:
                        found = term
            if found is None:
                raise IntakeWorkbenchError("term_not_found", 404)
            found["operative_candidate_review"] = {
                "status": "reviewer_confirmed_candidate"
                if confirmed and reviewer
                else "review_required",
                "reviewer_safe_id": reviewer,
                "confirmed": confirmed and bool(reviewer),
                "note": _text(payload.get("note"), 2_000),
                "reviewed_at": _now(),
            }
            self._event(record, "operative_candidate_reviewed", [term_id])
            return self.public(record)

        return self._mutate(operation)

    def ledger(self, payload: dict[str, Any]) -> dict[str, Any]:
        entries = _items(payload.get("entries"))
        permitted = {"alleged", "observed", "unknown"}
        result = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise IntakeWorkbenchError("ledger_entry_invalid")
            term = self._find_term(_safe_id(entry.get("term_id"), "term_id"))
            status = str(entry.get("compliance_status") or "unknown")
            if status not in permitted:
                raise IntakeWorkbenchError("compliance_status_invalid")
            result.append(
                {
                    "ledger_id": f"ledger_{uuid.uuid4().hex}",
                    "term": term,
                    "person_or_role": _text(entry.get("person_or_role"), 256),
                    "required_or_prohibited_conduct": _text(entry.get("conduct"), 2_000),
                    "frequency_or_date": _text(entry.get("frequency_or_date"), 256),
                    "conditions": _text(entry.get("conditions"), 2_000),
                    "exceptions": _text(entry.get("exceptions"), 2_000),
                    "related_evidence": [
                        _source_ref(value) for value in _items(entry.get("related_evidence"))
                    ],
                    "compliance_status": status,
                    "contradictory_records": [
                        _source_ref(value) for value in _items(entry.get("contradictory_records"))
                    ],
                    "reviewer_decision": _text(entry.get("reviewer_decision"), 2_000),
                    "contempt_or_willfulness": "not_determined",
                }
            )
        return {
            "status": "review_required",
            "review_required": True,
            "entries": result,
            "limitations": ["The ledger does not determine compliance, contempt, or willfulness."],
        }

    def receipt(self) -> dict[str, Any]:
        record = self.public(self._load())
        receipt = {
            "schema": "maine_family_law_llm.order_intelligence_receipt.v1",
            "revision": record["revision"],
            "orders_hash": _digest(record["orders"]),
            "graph_hash": _digest(record["edges"]),
            "review_history_tip_hash": str(record["review_history"][-1].get("event_hash") or ""),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _digest(receipt)
        return receipt

    def public(self, record: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(record)
        result.pop("scope_id", None)
        result["storage"] = {"local_only": True, "encrypted": True, "raw_paths_exposed": False}
        return result
