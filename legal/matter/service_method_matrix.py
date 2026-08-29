"""Encrypted, non-advisory service-method review matrices.

This work product keeps a reviewer-selected service-method label separate from
the private proof record, one resolver-verified authority card, and the facts
or exceptions that still need human review.  It does not determine effective
service, notice, timeliness, waiver, jurisdiction, or legal sufficiency.
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
_METHODS = {
    "personal_service",
    "mail_service",
    "electronic_service",
    "publication",
    "waiver",
    "other",
    "unknown",
}


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
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, limit: int = 2_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


def _page(value: Any, field: str) -> int:
    try:
        result = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise IntakeWorkbenchError(f"{field}_invalid") from exc
    if result < 0 or result > 100_000:
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _list(value: Any, field: str, *, limit: int = 25) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise IntakeWorkbenchError(f"{field}_invalid")
    return [_text(item, field, 1_000) for item in value if _text(item, field, 1_000, False)]


class ServiceMethodMatrixStore:
    schema = "maine_family_law_llm.service_method_matrix.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "18_PROCEDURE" / "service-method-matrices"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("service_method_matrix_store_unavailable", 409)
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
            raise IntakeWorkbenchError("service_method_matrix_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("matrices", [])
        state.setdefault("ledger", [])
        state.setdefault("revision", 0)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "filing_ready": False,
                "local_only": True,
                "service_effectiveness": "not_determined",
                "notice": "This matrix organizes reviewer-selected method, proof, authority, exceptions, and unresolved facts. It does not determine service, notice, waiver, timeliness, jurisdiction, or legal sufficiency.",
            }
        )
        return result

    @staticmethod
    def _records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        available: dict[str, dict[str, Any]] = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            digest = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and _HASH.fullmatch(digest):
                available[record_id] = row
        return available

    def _proof(self, raw: Any, records: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise IntakeWorkbenchError("service_proof_invalid")
        record_id = _text(raw.get("record_id"), "service_proof_record_id", 160)
        source_hash = _hash(raw.get("source_hash"), "service_proof_source_hash")
        record = records.get(record_id)
        if record is None or str(record.get("source_hash") or record.get("sha256") or "").casefold() != source_hash:
            raise IntakeWorkbenchError("service_proof_not_in_active_matter", 404)
        return {
            "record_id": record_id,
            "source_hash": source_hash,
            "title": _text(record.get("title") or record.get("source_locator") or record_id, "service_proof_title", 300),
            "page_number": _page(raw.get("page_number") or record.get("page_number") or 0, "service_proof_page"),
            "lane": "private_matter_record",
        }

    def _authority(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "authority_id": _id(raw.get("authority_id"), "service_authority_id"),
            "source_id": _text(raw.get("source_id"), "service_authority_source_id", 240),
            "source_hash": _hash(raw.get("source_hash"), "service_authority_source_hash"),
            "citation": _text(raw.get("citation"), "service_authority_citation", 500),
            "title": _text(raw.get("title"), "service_authority_title", 500),
            "exact_span": _text(raw.get("exact_span"), "service_authority_span", 4_000, False),
            "freshness_status": _text(raw.get("freshness_status"), "service_authority_freshness", 80, False) or "unknown",
            "lane": "official_authority",
        }

    def create(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]], authority: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("service_method_matrix_confirmation_required", 409)
        matrix_id = _id(payload.get("matrix_id"), "service_method_matrix_id")
        reviewer = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        method = str(payload.get("selected_method") or "unknown").strip().casefold()
        if method not in _METHODS:
            raise IntakeWorkbenchError("service_method_invalid")
        proof = self._proof(payload.get("proof"), self._records(records))
        matrix = {
            "matrix_id": matrix_id,
            "reviewer_safe_id": reviewer,
            "selected_method": method,
            "proof": proof,
            "authority": self._authority(authority),
            "exceptions": _list(payload.get("exceptions") or [], "service_exceptions"),
            "unresolved_facts": _list(payload.get("unresolved_facts") or [], "service_unresolved_facts"),
            "created_at": _now(),
            "review_required": True,
            "filing_ready": False,
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("matrix_id") == matrix_id for row in state["matrices"]):
                raise IntakeWorkbenchError("service_method_matrix_id_already_exists", 409)
            state["matrices"].append(matrix)
            event = {
                "event_id": f"service_method_matrix_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "create_service_method_matrix",
                "matrix_id": matrix_id,
                "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
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
            wanted = _id(matrix_id, "service_method_matrix_id")
            found = next((row for row in rows if row.get("matrix_id") == wanted), None)
            if found is None:
                raise IntakeWorkbenchError("service_method_matrix_not_found", 404)
            return {"matrix": found, "review_required": True, "local_only": True}
        return {"matrices": rows, "review_required": True, "local_only": True}

    def source(self, matrix_id: str, lane: str) -> dict[str, Any]:
        matrix = self.matrices(matrix_id)["matrix"]
        if lane == "private_matter_record":
            source = matrix["proof"]
        elif lane == "official_authority":
            source = matrix["authority"]
        else:
            raise IntakeWorkbenchError("service_method_matrix_lane_invalid")
        return {"matrix_id": matrix["matrix_id"], "source": source, "review_required": True}
