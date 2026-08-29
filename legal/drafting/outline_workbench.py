"""Encrypted, source-bound outline work products created before draft prose.

An outline is deliberately not a legal conclusion or filing.  It records the
reviewer's issue framing and the exact authority/evidence references selected
for later drafting, while keeping both source lanes distinct.
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


def _safe_id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, *, limit: int = 2_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


def _hash(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_required")
    return result


class OutlineWorkbenchStore:
    """A per-matter encrypted outline store; source files and draft prose stay separate."""

    schema = "maine_family_law_llm.outline_workbench.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "19_DRAFTING" / "outline-workbench"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("outline_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "outlines.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".outlines.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "outlines": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("outline_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        value.setdefault("outlines", [])
        value.setdefault("ledger", [])
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, outline_id: str, callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            state = self._load()
            result = callback(state)
            prior = str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else ""
            event = {"event_id": f"outline_{uuid.uuid4().hex}", "at": _now(), "action": action, "outline_id": outline_id, "previous_event_hash": prior, "review_required": True}
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
            return result

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update({
            "status": "review_required", "review_required": True, "local_only": True,
            "draft_prose_created": False, "filing_ready": False,
            "notice": "This source-bound outline is a review work product. It does not decide facts, law, jurisdiction, or filing readiness.",
        })
        return result

    @staticmethod
    def _active_records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").strip().casefold()
            if record_id and _HASH.fullmatch(source_hash):
                result[record_id] = row
        return result

    def create_outline(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        outline_id = _safe_id(payload.get("outline_id"), "outline_id")
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("outline_confirmation_required", 409)
        issue_id = _safe_id(payload.get("issue_id"), "issue_id")
        reviewer_safe_id = _safe_id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        issue_label = _text(payload.get("issue_label"), "issue_label", limit=300)
        purpose = _text(payload.get("purpose"), "purpose", limit=1_000, required=False)
        available = self._active_records(records)
        selected_evidence = payload.get("selected_evidence")
        if not isinstance(selected_evidence, list) or not selected_evidence or len(selected_evidence) > 100:
            raise IntakeWorkbenchError("selected_evidence_required")
        evidence: list[dict[str, Any]] = []
        known_evidence: set[str] = set()
        for raw in selected_evidence:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("selected_evidence_invalid")
            record_id = _text(raw.get("record_id"), "evidence_record_id", limit=120)
            provided_hash = _hash(raw.get("source_hash"), "evidence_source_hash")
            if record_id in known_evidence:
                raise IntakeWorkbenchError("duplicate_evidence_record")
            record = available.get(record_id)
            if record is None or str(record.get("source_hash") or record.get("sha256") or "").casefold() != provided_hash:
                raise IntakeWorkbenchError("evidence_source_not_in_active_matter", 404)
            known_evidence.add(record_id)
            evidence.append({
                "record_id": record_id, "source_hash": provided_hash,
                "title": _text(record.get("title") or record.get("source_locator") or record_id, "evidence_title", limit=300),
                "source_block": {"page_number": int(raw.get("page_number") or 0), "start_offset": int(raw.get("start_offset") or 0), "end_offset": int(raw.get("end_offset") or 0)},
                "lane": "private_matter_record",
            })
        selected_authority = payload.get("selected_authority")
        if not isinstance(selected_authority, list) or not selected_authority or len(selected_authority) > 100:
            raise IntakeWorkbenchError("selected_authority_required")
        authority: list[dict[str, Any]] = []
        known_authority: set[str] = set()
        for raw in selected_authority:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("selected_authority_invalid")
            authority_id = _safe_id(raw.get("authority_id"), "authority_id")
            if authority_id in known_authority:
                raise IntakeWorkbenchError("duplicate_authority_id")
            known_authority.add(authority_id)
            authority.append({
                "authority_id": authority_id,
                "source_id": _text(raw.get("source_id"), "authority_source_id", limit=240),
                "source_hash": _hash(raw.get("source_hash"), "authority_source_hash"),
                "citation": _text(raw.get("citation"), "authority_citation", limit=500),
                "title": _text(raw.get("title"), "authority_title", limit=500),
                "exact_span": _text(raw.get("exact_span"), "authority_exact_span", limit=2_000, required=False),
                "lane": "official_authority",
                "review_status": "not_independently_verified",
            })

        def callback(state: dict[str, Any]) -> dict[str, Any]:
            if any(str(item.get("outline_id") or "") == outline_id for item in state["outlines"]):
                raise IntakeWorkbenchError("outline_id_already_exists", 409)
            outline = {
                "outline_id": outline_id, "issue_id": issue_id, "issue_label": issue_label, "purpose": purpose,
                "reviewer_safe_id": reviewer_safe_id, "created_at": _now(), "authority": authority, "evidence": evidence,
                "sections": [
                    {"section": "issue", "content": issue_label, "status": "review_required"},
                    {"section": "authority", "content": f"{len(authority)} selected authority source(s); verify currentness and exact spans.", "status": "review_required"},
                    {"section": "evidence", "content": f"{len(evidence)} selected private record(s); verify attribution, context, and admissibility separately.", "status": "review_required"},
                    {"section": "open_questions", "content": "Add missing facts, counterevidence, and qualification review before prose.", "status": "review_required"},
                ],
                "review_required": True, "draft_prose_created": False, "filing_ready": False,
            }
            state["outlines"].append(outline)
            return self._public(outline)

        return self._mutate("create_outline", outline_id, callback)

    def outlines(self, outline_id: str = "") -> dict[str, Any]:
        state = self._load()
        rows = [self._public(item) for item in state["outlines"]]
        if outline_id:
            needle = _safe_id(outline_id, "outline_id")
            match = next((item for item in rows if item["outline_id"] == needle), None)
            if match is None:
                raise IntakeWorkbenchError("outline_not_found", 404)
            return {"outline": match, "review_required": True}
        return {"outlines": rows, "review_required": True, "local_only": True}

    def evidence_source(self, outline_id: str, record_id: str) -> dict[str, Any]:
        outline = self.outlines(outline_id)["outline"]
        source = next((item for item in outline["evidence"] if item["record_id"] == record_id), None)
        if source is None:
            raise IntakeWorkbenchError("outline_evidence_source_not_found", 404)
        return {"outline_id": outline["outline_id"], "source": source, "review_required": True}

    def authority_source(self, outline_id: str, authority_id: str) -> dict[str, Any]:
        outline = self.outlines(outline_id)["outline"]
        source = next((item for item in outline["authority"] if item["authority_id"] == authority_id), None)
        if source is None:
            raise IntakeWorkbenchError("outline_authority_source_not_found", 404)
        return {"outline_id": outline["outline_id"], "source": source, "review_required": True}
