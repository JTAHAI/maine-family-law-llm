"""Encrypted, fail-closed filing-package preflight review records.

The preflight is intentionally not a submission or certification mechanism.
It preserves exactly what the reviewer said was inspected and exposes every
missing confirmation as a blocker.  The canonical reviewed-filing packet and
its export controls remain separate gates.
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
_CHECKS = ("caption_confirmed", "names_confirmed", "signatures_confirmed", "format_confirmed", "redactions_confirmed", "privacy_review_complete", "human_review_complete")


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


def _page(value: Any) -> int:
    try:
        page = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise IntakeWorkbenchError("preflight_attachment_page_invalid") from exc
    if page < 0 or page > 100_000:
        raise IntakeWorkbenchError("preflight_attachment_page_invalid")
    return page


class FilingPreflightStore:
    schema = "maine_family_law_llm.filing_preflight.v2"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "38_FILING_READINESS" / "preflight-v2"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("filing_preflight_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "preflights.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".preflights.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "preflights": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("filing_preflight_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        value.setdefault("preflights", []); value.setdefault("ledger", []); value.setdefault("revision", 0)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.update({"status": "review_required", "review_required": True, "filing_ready": False, "local_only": True, "submission_attempted": False, "notice": "This preflight exposes review blockers only. It does not approve a filing, submit anything, or bypass the canonical reviewed-filing packet gate."})
        return result

    @staticmethod
    def _records(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in records:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and _HASH.fullmatch(source_hash):
                result[record_id] = row
        return result

    def _attachments(self, raw: Any, records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(raw, list) or not raw or len(raw) > 100:
            raise IntakeWorkbenchError("preflight_attachments_invalid")
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise IntakeWorkbenchError("preflight_attachment_invalid")
            record_id = _text(item.get("record_id"), "preflight_record_id", 160)
            source_hash = str(item.get("source_hash") or "").casefold()
            if record_id in seen or not _HASH.fullmatch(source_hash):
                raise IntakeWorkbenchError("preflight_attachment_invalid")
            record = records.get(record_id)
            if record is None or str(record.get("source_hash") or record.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("preflight_attachment_not_in_active_matter", 404)
            seen.add(record_id)
            output.append({"record_id": record_id, "source_hash": source_hash, "title": _text(record.get("title") or record.get("source_locator") or record_id, "preflight_attachment_title", 300), "page_number": _page(item.get("page_number") or record.get("page_number") or 0), "declared_format": _text(item.get("declared_format") or "unknown", "preflight_declared_format", 80), "lane": "private_matter_record"})
        return output

    @staticmethod
    def _forms(forms: Any) -> list[dict[str, Any]]:
        if not isinstance(forms, list) or len(forms) > 50:
            raise IntakeWorkbenchError("preflight_forms_invalid")
        output: list[dict[str, Any]] = []
        for item in forms:
            if not isinstance(item, dict):
                raise IntakeWorkbenchError("preflight_form_invalid")
            source_hash = str(item.get("source_hash") or "").casefold()
            if not _HASH.fullmatch(source_hash):
                raise IntakeWorkbenchError("preflight_form_invalid")
            output.append({"authority_id": _id(item.get("authority_id"), "preflight_form_authority_id"), "source_id": _text(item.get("source_id"), "preflight_form_source_id", 240), "source_hash": source_hash, "citation": _text(item.get("citation"), "preflight_form_citation", 500), "title": _text(item.get("title"), "preflight_form_title", 500), "freshness_status": _text(item.get("freshness_status"), "preflight_form_freshness", 80, False) or "unknown", "lane": "official_authority"})
        return output

    @staticmethod
    def _checks(raw: Any) -> dict[str, bool]:
        if not isinstance(raw, dict):
            raise IntakeWorkbenchError("preflight_checks_invalid")
        return {name: raw.get(name) is True for name in _CHECKS}

    @staticmethod
    def _blockers(entry: dict[str, Any]) -> list[str]:
        blockers = [name for name, confirmed in entry["checks"].items() if not confirmed]
        if not entry["attachments"]:
            blockers.append("missing_attachments")
        if not entry["forms"]:
            blockers.append("forms_not_checked")
        if any(form.get("freshness_status") not in {"fresh", "current"} for form in entry["forms"]):
            blockers.append("stale_or_unknown_form")
        if not entry["canonical_packet_gate_seen"]:
            blockers.append("canonical_reviewed_filing_packet_not_seen")
        return sorted(set(blockers))

    def create(self, payload: dict[str, Any], *, records: Iterable[dict[str, Any]], forms: list[dict[str, Any]]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("filing_preflight_confirmation_required", 409)
        preflight_id = _id(payload.get("preflight_id"), "filing_preflight_id")
        entry = {"preflight_id": preflight_id, "reviewer_safe_id": _id(payload.get("reviewer_safe_id"), "reviewer_safe_id"), "caption_label": _text(payload.get("caption_label"), "preflight_caption_label", 300), "attachments": self._attachments(payload.get("attachments"), self._records(records)), "forms": self._forms(forms), "checks": self._checks(payload.get("checks")), "canonical_packet_gate_seen": payload.get("canonical_packet_gate_seen") is True, "created_at": _now(), "review_required": True, "filing_ready": False}
        entry["blockers"] = self._blockers(entry)
        entry["preflight_hash"] = _digest({key: value for key, value in entry.items() if key != "created_at"})
        with exclusive_file_lock(self.lock):
            state = self._load()
            if any(row.get("preflight_id") == preflight_id for row in state["preflights"]):
                raise IntakeWorkbenchError("filing_preflight_id_already_exists", 409)
            state["preflights"].append(entry)
            event = {"event_id": f"filing_preflight_{uuid.uuid4().hex}", "at": _now(), "action": "create_filing_preflight", "preflight_id": preflight_id, "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "", "review_required": True}
            event["event_hash"] = _digest(event); state["ledger"].append(event); state["revision"] = int(state.get("revision") or 0) + 1; self._save(state)
        return self._public(entry)

    def preflights(self, preflight_id: str = "") -> dict[str, Any]:
        rows = [self._public(row) for row in self._load()["preflights"]]
        if preflight_id:
            found = next((row for row in rows if row.get("preflight_id") == _id(preflight_id, "filing_preflight_id")), None)
            if found is None:
                raise IntakeWorkbenchError("filing_preflight_not_found", 404)
            return {"preflight": found, "review_required": True, "local_only": True}
        return {"preflights": rows, "review_required": True, "local_only": True}

    def source(self, preflight_id: str, lane: str, source_id: str) -> dict[str, Any]:
        entry = self.preflights(preflight_id)["preflight"]
        if lane == "private_matter_record":
            source = next((row for row in entry["attachments"] if row.get("record_id") == source_id), None)
        elif lane == "official_authority":
            source = next((row for row in entry["forms"] if row.get("authority_id") == source_id), None)
        else:
            raise IntakeWorkbenchError("filing_preflight_lane_invalid")
        if source is None:
            raise IntakeWorkbenchError("filing_preflight_source_not_found", 404)
        return {"preflight_id": entry["preflight_id"], "source": source, "review_required": True}
