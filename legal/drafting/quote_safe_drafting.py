"""Review-first, encrypted quote insertion receipts for local drafting."""

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
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _text(value: Any, name: str, limit: int = 8_000) -> str:
    result = str(value or "").replace("\x00", "").strip()
    if not result:
        raise IntakeWorkbenchError(f"{name}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{name}_too_long")
    return result


def _id(value: Any, name: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{name}_invalid")
    return result


def _hash(value: Any, name: str) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError(f"{name}_required")
    return result


def _normal(value: str) -> str:
    return " ".join(value.casefold().replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'").split())


class QuoteSafeDraftStore:
    schema = "maine_family_law_llm.quote_safe_drafting.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve(); self.root = self.case_root / "19_DRAFTING" / "quote-safe-drafting"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("quote_safe_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path: return self.root / "quote-receipts.json.enc"
    @property
    def lock(self) -> Path: return self.root / ".quote-receipts.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema": self.schema, "scope": self.scope, "receipts": [], "ledger": [], "revision": 0}
        try: state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc: raise IntakeWorkbenchError("quote_safe_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope: raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("receipts", []); state.setdefault("ledger", []); return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, receipt_id: str, callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            state = self._load(); result = callback(state); previous = str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else ""
            event = {"event_id": f"quote_{uuid.uuid4().hex}", "at": _now(), "action": "create_quote_receipt", "receipt_id": receipt_id, "previous_event_hash": previous, "review_required": True}
            event["event_hash"] = _digest(event); state["ledger"].append(event); state["revision"] = int(state.get("revision") or 0) + 1; self._save(state); return result

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value); result.pop("scope", None); result.update({"status": "review_required", "review_required": True, "filing_ready": False, "local_only": True, "notice": "The quote match only verifies the selected source span. It does not determine legal effect, context, quotation completeness, or filing readiness."}); return result

    def create(self, payload: dict[str, Any], *, document: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True: raise IntakeWorkbenchError("quote_confirmation_required", 409)
        reviewer_safe_id = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        document_id = _text(document.get("document_id"), "document_id", 80); revision_id = _text(document.get("current_revision_id"), "revision_id", 80); content = _text(document.get("content"), "document_content", 1_500_000)
        selected_text = _text(payload.get("selected_text"), "selected_text", 4_000); quote_text = _text(payload.get("quote_text"), "quote_text", 4_000)
        authority = payload.get("authority")
        if not isinstance(authority, dict): raise IntakeWorkbenchError("quote_authority_required")
        source_id = _text(authority.get("source_id"), "quote_source_id", 240); source_hash = _hash(authority.get("source_hash"), "quote_source_hash")
        exact_span = _text(authority.get("exact_span"), "quote_exact_span", 8_000); citation = _text(authority.get("citation"), "quote_citation", 500)
        freshness = str(authority.get("freshness_status") or "unknown").casefold()
        if freshness in {"stale", "stale_unknown", "superseded"}: raise IntakeWorkbenchError("quote_authority_stale", 409)
        if quote_text in exact_span: quote_status = "exact"
        elif _normal(quote_text) in _normal(exact_span): quote_status = "normalized"
        else: raise IntakeWorkbenchError("quote_not_found_in_selected_source_span", 409)
        if quote_status == "normalized" and payload.get("normalized_quote_approved") is not True: raise IntakeWorkbenchError("normalized_quote_approval_required", 409)
        start = content.find(selected_text)
        if start < 0: raise IntakeWorkbenchError("selected_text_not_in_current_draft", 409)
        if content.find(selected_text, start + 1) >= 0: raise IntakeWorkbenchError("selected_text_occurrence_required", 409)
        end = start + len(selected_text); quoted = '“' + quote_text + '”'
        proposed = content[:start] + quoted + content[end:]
        receipt_id = "quote_insert_" + _digest({"document": document_id, "revision": revision_id, "start": start, "source": source_hash, "quote": quote_text})[:24]
        def callback(state: dict[str, Any]) -> dict[str, Any]:
            state["receipts"] = [row for row in state["receipts"] if str(row.get("receipt_id") or "") != receipt_id]
            receipt = {"receipt_id": receipt_id, "document_id": document_id, "revision_id": revision_id, "document_content_sha256": hashlib.sha256(content.encode()).hexdigest(), "reviewer_safe_id": reviewer_safe_id, "selection": {"selected_text": selected_text, "start_offset": start, "end_offset": end}, "quote": {"text": quote_text, "status": quote_status, "source_id": source_id, "source_hash": source_hash, "citation": citation, "exact_span": exact_span, "lane": "official_authority"}, "proposed_content": proposed, "proposed_content_sha256": hashlib.sha256(proposed.encode()).hexdigest(), "created_at": _now(), "review_required": True, "filing_ready": False}
            state["receipts"].append(receipt); return self._public(receipt)
        return self._mutate(receipt_id, callback)

    def receipt(self, document_id: str, receipt_id: str) -> dict[str, Any]:
        found = next((row for row in self._load()["receipts"] if str(row.get("document_id") or "") == document_id and str(row.get("receipt_id") or "") == receipt_id), None)
        if found is None: raise IntakeWorkbenchError("quote_receipt_not_found", 404)
        return self._public(found)
