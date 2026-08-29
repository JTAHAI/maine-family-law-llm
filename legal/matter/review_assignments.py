"""Encrypted local review assignments with evidence-bound completion.

This is a matter-local queue only.  It does not notify, message, provision an
account, authorize a reviewer, or treat completion as approval, legal advice,
or filing readiness.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_ROLES = frozenset({"reviewer", "attorney", "paralegal", "administrator", "records_reviewer"})
_SCOPE_KINDS = frozenset({"matter", "record", "claim", "draft", "artifact", "reviewer_bundle"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip().casefold()
    if not _ID.fullmatch(text):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return text


def _hash(value: Any, field: str) -> str:
    text = str(value or "").strip().casefold()
    if not _HASH.fullmatch(text):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return text


def _note(value: Any, field: str, maximum: int = 4_000) -> str:
    text = str(value or "").strip()
    if not text:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(text) > maximum:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return text


def _due_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise IntakeWorkbenchError("assignment_due_date_invalid") from exc


def _scope(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("scope_kind") or "").strip().casefold()
    if kind not in _SCOPE_KINDS:
        raise IntakeWorkbenchError("assignment_scope_kind_invalid")
    scope = {"kind": kind, "scope_id": _id(payload.get("scope_id"), "assignment_scope_id"), "scope_hash": _hash(payload.get("scope_hash"), "assignment_scope_hash")}
    if kind == "record":
        scope["source_drill_down"] = {"route": f"/api/records/{scope['scope_id']}/integrity", "review_required": True}
    else:
        scope["source_drill_down"] = {"kind": kind, "scope_id": scope["scope_id"], "scope_hash": scope["scope_hash"], "review_required": True}
    return scope


def _required_evidence(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > 100:
        raise IntakeWorkbenchError("assignment_required_evidence_invalid")
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise IntakeWorkbenchError("assignment_required_evidence_invalid")
        rows.append({"evidence_id": _id(item.get("evidence_id"), "evidence_id"), "evidence_hash": _hash(item.get("evidence_hash"), "evidence_hash"), "kind": str(item.get("kind") or "source").strip()[:80]})
    if len({row["evidence_id"] for row in rows}) != len(rows):
        raise IntakeWorkbenchError("assignment_required_evidence_duplicate")
    return rows


class ReviewAssignmentStore:
    schema = "maine_family_law_llm.review_assignments.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve(); self.root = self.case_root / "46_REVIEW_ASSIGNMENTS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("review_assignment_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path: return self.root / "assignments.json.enc"
    @property
    def lock(self) -> Path: return self.root / ".assignments.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema": self.schema, "scope": self.scope, "assignments": [], "history": [], "revision": 0}
        try: value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc: raise IntakeWorkbenchError("review_assignment_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope or not isinstance(value.get("assignments"), list) or not isinstance(value.get("history"), list): raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None: atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, ids: list[str], operation: Callable[[dict[str, Any]], Any]) -> Any:
        with exclusive_file_lock(self.lock):
            value = self._load(); result = operation(value)
            event = {"event_id": f"review_assignment_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": ids, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}; event["hash"] = _digest(event)
            value["history"].append(event); value["revision"] += 1; self._save(value); return result

    @staticmethod
    def _assignment(value: dict[str, Any], assignment_id: str) -> dict[str, Any]:
        for item in value["assignments"]:
            if item.get("assignment_id") == assignment_id: return item
        raise IntakeWorkbenchError("review_assignment_not_found", 404)

    @staticmethod
    def _public(item: dict[str, Any], *, include_notes: bool) -> dict[str, Any]:
        result = deepcopy(item)
        if not include_notes:
            result.pop("instructions", None); result.pop("completion_note", None)
        result.update({"review_required": True, "local_only": True, "external_messaging": False, "automatic_approval": False})
        return result

    def inventory(self, *, include_completed: bool = False) -> dict[str, Any]:
        value = self._load(); items = [row for row in value["assignments"] if include_completed or row.get("status") != "completed_review_required"]
        items.sort(key=lambda row: (row.get("due_date", ""), row.get("assignment_id", "")))
        return {"schema": self.schema, "assignments": [self._public(row, include_notes=False) for row in items], "revision": value["revision"], "history_hash": _digest(value["history"]), "review_required": True, "local_only": True, "external_messaging": False}

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        assignment_id = _id(payload.get("assignment_id"), "assignment_id"); role = str(payload.get("required_role") or "").strip().casefold()
        if role not in _ROLES: raise IntakeWorkbenchError("assignment_required_role_invalid")
        assignee = _id(payload.get("assignee_safe_id"), "assignee_safe_id"); due = _due_date(payload.get("due_date")); scope = _scope(payload); evidence = _required_evidence(payload.get("required_evidence")); instructions = _note(payload.get("instructions"), "assignment_instructions")
        def operation(value: dict[str, Any]) -> dict[str, Any]:
            if any(row.get("assignment_id") == assignment_id for row in value["assignments"]): raise IntakeWorkbenchError("duplicate_review_assignment_id", 409)
            item = {"assignment_id": assignment_id, "required_role": role, "assignee_safe_id": assignee, "due_date": due, "scope": scope, "required_evidence": evidence, "instructions": instructions, "status": "assigned_review_required", "created_at": _now(), "review_required": True}; item["assignment_hash"] = _digest(item); value["assignments"].append(item); return deepcopy(item)
        return self._public(self._mutate("review_assignment_created", [assignment_id, assignee], operation), include_notes=True)

    def claim(self, assignment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        assignment = _id(assignment_id, "assignment_id"); reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        def operation(value: dict[str, Any]) -> dict[str, Any]:
            item = self._assignment(value, assignment)
            if item["status"] != "assigned_review_required": raise IntakeWorkbenchError("review_assignment_not_claimable", 409)
            if reviewer != item["assignee_safe_id"]: raise IntakeWorkbenchError("review_assignment_assignee_mismatch", 403)
            item["status"] = "claimed_review_required"; item["claimed_by_safe_id"] = reviewer; item["claimed_at"] = _now(); item["assignment_hash"] = _digest({key: row for key, row in item.items() if key != "assignment_hash"}); return deepcopy(item)
        return self._public(self._mutate("review_assignment_claimed", [assignment, reviewer], operation), include_notes=True)

    def complete(self, assignment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        assignment = _id(assignment_id, "assignment_id"); reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id"); note = _note(payload.get("completion_note"), "assignment_completion_note")
        acknowledged = payload.get("acknowledged_evidence_ids")
        if not isinstance(acknowledged, list): raise IntakeWorkbenchError("assignment_evidence_acknowledgement_invalid")
        acknowledged_ids = {_id(item, "acknowledged_evidence_id") for item in acknowledged}
        def operation(value: dict[str, Any]) -> dict[str, Any]:
            item = self._assignment(value, assignment)
            if item["status"] != "claimed_review_required" or item.get("claimed_by_safe_id") != reviewer: raise IntakeWorkbenchError("review_assignment_not_owned", 409)
            required = {row["evidence_id"] for row in item["required_evidence"]}
            if required != acknowledged_ids: raise IntakeWorkbenchError("assignment_required_evidence_unacknowledged", 409)
            item.update({"status": "completed_review_required", "completed_at": _now(), "completion_note": note, "completed_by_safe_id": reviewer, "completion_is_not_approval": True}); item["assignment_hash"] = _digest({key: row for key, row in item.items() if key != "assignment_hash"}); return deepcopy(item)
        return self._public(self._mutate("review_assignment_completed", [assignment, reviewer], operation), include_notes=True)

    def get(self, assignment_id: str) -> dict[str, Any]: return self._public(self._assignment(self._load(), _id(assignment_id, "assignment_id")), include_notes=True)
