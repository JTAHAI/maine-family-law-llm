"""Encrypted, non-predictive matrices for reviewer comparison of competing positions.

The matrix preserves the distinction between a position someone may advance,
the sources selected for review, weaknesses, and missing proof.  It does not
weigh credibility, decide facts or law, or predict a court outcome.
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
from typing import Any, Iterable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _hash(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_required")
    return result


def _text(value: Any, field: str, *, limit: int = 4_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


class ArgumentMatrixStore:
    """Matter-private storage for explicitly non-predictive position comparison."""

    schema = "maine_family_law_llm.argument_matrix.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "19_DRAFTING" / "argument-matrices"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("argument_matrix_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "matrices.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".matrices.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "matrices": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("argument_matrix_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("matrices", [])
        state.setdefault("ledger", [])
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "filing_ready": False,
                "local_only": True,
                "outcome_prediction": False,
                "notice": "This matrix organizes reviewer-entered competing positions and source references. It does not decide facts, credibility, law, jurisdiction, legal sufficiency, or likely outcomes.",
            }
        )
        return result

    @staticmethod
    def _active_records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and _HASH.fullmatch(source_hash):
                result[record_id] = row
        return result

    def _evidence(self, values: Any, available: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(values, list) or len(values) > 25:
            raise IntakeWorkbenchError("position_evidence_invalid")
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in values:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("position_evidence_invalid")
            record_id = _text(raw.get("record_id"), "evidence_record_id", limit=160)
            source_hash = _hash(raw.get("source_hash"), "evidence_source_hash")
            if record_id in seen:
                raise IntakeWorkbenchError("duplicate_position_evidence")
            record = available.get(record_id)
            if record is None or str(record.get("source_hash") or record.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("argument_matrix_evidence_not_in_active_matter", 404)
            seen.add(record_id)
            result.append(
                {
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "title": _text(record.get("title") or record.get("source_locator") or record_id, "evidence_title", limit=300),
                    "page_number": max(0, int(raw.get("page_number") or record.get("page_number") or 0)),
                    "lane": "private_matter_record",
                }
            )
        return result

    def _authority(self, values: Any) -> list[dict[str, Any]]:
        if not isinstance(values, list) or len(values) > 25:
            raise IntakeWorkbenchError("position_authority_invalid")
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in values:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("position_authority_invalid")
            authority_id = _id(raw.get("authority_id"), "authority_id")
            if authority_id in seen:
                raise IntakeWorkbenchError("duplicate_position_authority")
            seen.add(authority_id)
            result.append(
                {
                    "authority_id": authority_id,
                    "source_id": _text(raw.get("source_id"), "authority_source_id", limit=240),
                    "source_hash": _hash(raw.get("source_hash"), "authority_source_hash"),
                    "citation": _text(raw.get("citation"), "authority_citation", limit=500),
                    "title": _text(raw.get("title"), "authority_title", limit=500),
                    "exact_span": _text(raw.get("exact_span"), "authority_exact_span", limit=4_000, required=False),
                    "freshness_status": _text(raw.get("freshness_status"), "authority_freshness", limit=80, required=False) or "unknown",
                    "lane": "official_authority",
                }
            )
        return result

    @staticmethod
    def _notes(values: Any, field: str) -> list[str]:
        if not isinstance(values, list) or len(values) > 30:
            raise IntakeWorkbenchError(f"{field}_invalid")
        result: list[str] = []
        for raw in values:
            note = _text(raw, field, limit=1_000)
            if note.casefold() not in {item.casefold() for item in result}:
                result.append(note)
        return result

    def create(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("argument_matrix_confirmation_required", 409)
        matrix_id = _id(payload.get("matrix_id"), "matrix_id")
        reviewer_safe_id = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        issue_label = _text(payload.get("issue_label"), "issue_label", limit=300)
        raw_positions = payload.get("positions")
        if not isinstance(raw_positions, list) or not 2 <= len(raw_positions) <= 8:
            raise IntakeWorkbenchError("competing_positions_required")
        available = self._active_records(records)
        positions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_positions:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("position_invalid")
            position_id = _id(raw.get("position_id"), "position_id")
            if position_id in seen:
                raise IntakeWorkbenchError("duplicate_position_id")
            seen.add(position_id)
            evidence = self._evidence(raw.get("supporting_evidence") or [], available)
            authority = self._authority(raw.get("supporting_authority") or [])
            if not evidence and not authority:
                raise IntakeWorkbenchError("position_source_required")
            positions.append(
                {
                    "position_id": position_id,
                    "label": _text(raw.get("label"), "position_label", limit=300),
                    "statement": _text(raw.get("statement"), "position_statement", limit=4_000),
                    "supporting_evidence": evidence,
                    "supporting_authority": authority,
                    "weaknesses": self._notes(raw.get("weaknesses") or [], "position_weakness"),
                    "missing_proof": self._notes(raw.get("missing_proof") or [], "position_missing_proof"),
                    "review_required": True,
                }
            )
        if not any(position["weaknesses"] or position["missing_proof"] for position in positions):
            raise IntakeWorkbenchError("weakness_or_missing_proof_required")
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(str(row.get("matrix_id") or "") == matrix_id for row in state["matrices"]):
                raise IntakeWorkbenchError("argument_matrix_id_already_exists", 409)
            matrix = {
                "matrix_id": matrix_id,
                "issue_label": issue_label,
                "reviewer_safe_id": reviewer_safe_id,
                "positions": positions,
                "created_at": _now(),
                "review_required": True,
                "filing_ready": False,
            }
            state["matrices"].append(matrix)
            prior = str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else ""
            event = {
                "event_id": f"argument_matrix_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "create_argument_matrix",
                "matrix_id": matrix_id,
                "previous_event_hash": prior,
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
            return self._public(matrix)

    def matrices(self, matrix_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["matrices"]]
        if matrix_id:
            needle = _id(matrix_id, "matrix_id")
            match = next((row for row in rows if row.get("matrix_id") == needle), None)
            if match is None:
                raise IntakeWorkbenchError("argument_matrix_not_found", 404)
            return {"matrix": match, "review_required": True}
        return {"matrices": rows, "review_required": True, "local_only": True}

    def source(self, matrix_id: str, position_id: str, lane: str, source_id: str) -> dict[str, Any]:
        matrix = self.matrices(matrix_id)["matrix"]
        position = next((row for row in matrix["positions"] if row.get("position_id") == _id(position_id, "position_id")), None)
        if position is None:
            raise IntakeWorkbenchError("argument_matrix_position_not_found", 404)
        if lane == "private_matter_record":
            source = next((row for row in position["supporting_evidence"] if row.get("record_id") == source_id), None)
        elif lane == "official_authority":
            source = next((row for row in position["supporting_authority"] if row.get("authority_id") == source_id), None)
        else:
            raise IntakeWorkbenchError("argument_matrix_lane_invalid")
        if source is None:
            raise IntakeWorkbenchError("argument_matrix_source_not_found", 404)
        return {"matrix_id": matrix["matrix_id"], "position_id": position["position_id"], "source": source, "review_required": True}
