"""Encrypted, non-advisory procedure-pathway review checklists."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_CASE_TYPES = {"family_matter", "divorce_with_children", "parental_rights", "protection", "post_judgment", "unknown"}
_POSTURES = {"initial_complaint", "temporary_order", "final_order", "post_judgment", "enforcement", "appeal", "unknown"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, limit: int = 1_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


class ProcedurePathwayStore:
    schema = "maine_family_law_llm.procedure_pathway.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "18_PROCEDURE" / "pathways"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("procedure_pathway_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "pathways.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".pathways.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "pathways": [], "ledger": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("procedure_pathway_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("pathways", []); state.setdefault("ledger", [])
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.update({"status": "review_required", "review_required": True, "filing_ready": False, "local_only": True, "legal_conclusion": "not_determined", "notice": "This is a source-bound procedural review checklist. It does not decide venue, jurisdiction, filing requirements, deadlines, service sufficiency, legal effect, or an outcome."})
        return result

    @staticmethod
    def _records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and _HASH.fullmatch(source_hash):
                result[record_id] = row
        return result

    def _orders(self, values: Any, records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(values, list) or len(values) > 50:
            raise IntakeWorkbenchError("existing_orders_invalid")
        result = []; seen = set()
        for raw in values:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("existing_orders_invalid")
            record_id = _text(raw.get("record_id"), "order_record_id", 160)
            source_hash = str(raw.get("source_hash") or "").casefold()
            if record_id in seen or not _HASH.fullmatch(source_hash):
                raise IntakeWorkbenchError("existing_order_invalid")
            row = records.get(record_id)
            if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("existing_order_not_in_active_matter", 404)
            seen.add(record_id)
            result.append({"record_id": record_id, "source_hash": source_hash, "title": _text(row.get("title") or row.get("source_locator") or record_id, "order_title", 300), "page_number": max(0, int(raw.get("page_number") or row.get("page_number") or 0)), "lane": "private_matter_record"})
        return result

    @staticmethod
    def _steps(case_type: str, posture: str, order_count: int) -> list[dict[str, str]]:
        steps = [
            {"step_id": "confirm_context", "label": "Confirm case type, posture, and venue facts", "why": "These are user-entered review inputs, not determinations."},
            {"step_id": "inspect_orders", "label": "Inspect known operative-order records", "why": "Review the exact terms and whether additional or superseding orders may exist."},
            {"step_id": "check_authority", "label": "Review the selected current official authority source", "why": "Confirm the source’s freshness, scope, and exact language."},
            {"step_id": "check_service_notice", "label": "Review service, notice, and proof records", "why": "Do not infer method, completion, or sufficiency from this checklist."},
            {"step_id": "check_forms_and_deadlines", "label": "Check current forms and candidate dates separately", "why": "A form or date requires its own freshness and human-review path."},
            {"step_id": "record_open_questions", "label": "Record missing records and unresolved facts", "why": "The checklist cannot fill gaps or decide a procedural consequence."},
        ]
        if posture == "initial_complaint":
            steps.insert(3, {"step_id": "starting_papers", "label": "Identify candidate starting papers and required review", "why": "Confirm against current official sources and the actual matter record."})
        elif posture == "temporary_order":
            steps.insert(3, {"step_id": "temporary_scope", "label": "Inspect temporary-order requests and prior orders", "why": "Scope, notice, and evidentiary support remain for human review."})
        elif posture in {"post_judgment", "enforcement"}:
            steps.insert(3, {"step_id": "change_or_compliance", "label": "Compare the asserted change or compliance issue to exact order terms", "why": "The checklist does not decide whether a standard is met."})
        elif posture == "appeal":
            steps.insert(3, {"step_id": "record_preservation", "label": "Identify record, transcript, and preservation questions", "why": "Do not infer reviewability or appellate jurisdiction."})
        return [{**step, "status": "review_required"} for step in steps]

    def create(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]], authority: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("procedure_pathway_confirmation_required", 409)
        pathway_id = _id(payload.get("pathway_id"), "pathway_id")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        case_type = str(payload.get("case_type") or "unknown").strip().casefold()
        posture = str(payload.get("posture") or "unknown").strip().casefold()
        if case_type not in _CASE_TYPES or posture not in _POSTURES:
            raise IntakeWorkbenchError("procedure_pathway_context_invalid")
        venue_label = _text(payload.get("venue_label"), "venue_label", 300)
        source_id = _text(authority.get("source_id"), "authority_source_id", 240)
        source_hash = str(authority.get("source_hash") or "").casefold()
        if not _HASH.fullmatch(source_hash):
            raise IntakeWorkbenchError("procedure_pathway_authority_invalid", 409)
        orders = self._orders(payload.get("existing_orders") or [], self._records(records))
        authority_ref = {"authority_id": _id(authority.get("authority_id"), "authority_id"), "source_id": source_id, "source_hash": source_hash, "citation": _text(authority.get("citation"), "authority_citation", 500), "title": _text(authority.get("title"), "authority_title", 500), "exact_span": _text(authority.get("exact_span"), "authority_span", 4_000, False), "freshness_status": _text(authority.get("freshness_status"), "authority_freshness", 80, False) or "unknown", "lane": "official_authority"}
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("pathway_id") == pathway_id for row in state["pathways"]):
                raise IntakeWorkbenchError("procedure_pathway_id_already_exists", 409)
            pathway = {"pathway_id": pathway_id, "reviewer_safe_id": reviewer, "case_type": case_type, "posture": posture, "venue_label": venue_label, "existing_orders": orders, "authority": authority_ref, "steps": self._steps(case_type, posture, len(orders)), "created_at": _now(), "review_required": True, "filing_ready": False}
            state["pathways"].append(pathway)
            event = {"event_id": f"procedure_pathway_{uuid.uuid4().hex}", "at": _now(), "action": "create_procedure_pathway", "pathway_id": pathway_id, "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "", "review_required": True}
            event["event_hash"] = _digest(event); state["ledger"].append(event); state["revision"] = int(state.get("revision") or 0) + 1; self._save(state)
            return self._public(pathway)

    def pathways(self, pathway_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["pathways"]]
        if pathway_id:
            found = next((row for row in rows if row.get("pathway_id") == _id(pathway_id, "pathway_id")), None)
            if found is None:
                raise IntakeWorkbenchError("procedure_pathway_not_found", 404)
            return {"pathway": found, "review_required": True}
        return {"pathways": rows, "review_required": True, "local_only": True}

    def source(self, pathway_id: str, lane: str, source_id: str) -> dict[str, Any]:
        pathway = self.pathways(pathway_id)["pathway"]
        if lane == "private_matter_record":
            source = next((row for row in pathway["existing_orders"] if row.get("record_id") == source_id), None)
        elif lane == "official_authority":
            source = pathway["authority"] if pathway["authority"].get("authority_id") == source_id else None
        else:
            raise IntakeWorkbenchError("procedure_pathway_lane_invalid")
        if source is None:
            raise IntakeWorkbenchError("procedure_pathway_source_not_found", 404)
        return {"pathway_id": pathway["pathway_id"], "source": source, "review_required": True}
