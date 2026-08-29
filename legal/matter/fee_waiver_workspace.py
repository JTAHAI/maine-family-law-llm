"""Encrypted, non-eligibility fee and waiver information workspaces."""

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


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _text(value: Any, field: str, limit: int = 2_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


class FeeWaiverWorkspaceStore:
    schema = "maine_family_law_llm.fee_waiver_workspace.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve(); self.root = self.case_root / "38_FILING_READINESS" / "fee-waiver"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("fee_waiver_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path: return self.root / "workspaces.json.enc"
    @property
    def lock(self) -> Path: return self.root / ".workspaces.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema": self.schema, "scope": self.scope, "workspaces": [], "ledger": [], "revision": 0}
        try: value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True))
        except Exception as exc: raise IntakeWorkbenchError("fee_waiver_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope: raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        value.setdefault("workspaces", []); value.setdefault("ledger", []); value.setdefault("revision", 0); return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value); result.update({"status": "review_required", "review_required": True, "filing_ready": False, "local_only": True, "eligibility": "not_determined", "notice": "This workspace organizes selected official information and user-entered facts. It does not calculate fees, determine waiver eligibility, complete a form, or make a filing ready."}); return result

    @staticmethod
    def _authority(value: dict[str, Any]) -> dict[str, Any]:
        digest = str(value.get("source_hash") or "").casefold()
        if not _HASH.fullmatch(digest): raise IntakeWorkbenchError("fee_waiver_authority_invalid", 409)
        return {"authority_id": _id(value.get("authority_id"), "fee_waiver_authority_id"), "source_id": _text(value.get("source_id"), "fee_waiver_source_id", 240), "source_hash": digest, "citation": _text(value.get("citation"), "fee_waiver_citation", 500), "title": _text(value.get("title"), "fee_waiver_title", 500), "exact_span": _text(value.get("exact_span"), "fee_waiver_span", 4_000, False), "freshness_status": _text(value.get("freshness_status"), "fee_waiver_freshness", 80, False) or "unknown", "lane": "official_authority"}

    @staticmethod
    def _facts(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list) or len(value) > 40: raise IntakeWorkbenchError("fee_waiver_facts_invalid")
        output=[]; seen=set()
        for raw in value:
            if not isinstance(raw, dict): raise IntakeWorkbenchError("fee_waiver_fact_invalid")
            fact_id = _id(raw.get("fact_id"), "fee_waiver_fact_id")
            if fact_id in seen: raise IntakeWorkbenchError("fee_waiver_fact_duplicate")
            seen.add(fact_id); output.append({"fact_id": fact_id, "label": _text(raw.get("label"), "fee_waiver_fact_label", 300), "user_entered_value": _text(raw.get("user_entered_value"), "fee_waiver_fact_value", 2_000), "state": "user_entered_unverified"})
        return output

    def create(self, payload: dict[str, Any], *, authority: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True: raise IntakeWorkbenchError("fee_waiver_confirmation_required", 409)
        workspace_id = _id(payload.get("workspace_id"), "fee_waiver_workspace_id")
        entry={"workspace_id": workspace_id, "reviewer_safe_id": _id(payload.get("reviewer_safe_id"), "reviewer_safe_id"), "purpose_label": _text(payload.get("purpose_label"), "fee_waiver_purpose_label", 300), "authority": self._authority(authority), "facts": self._facts(payload.get("facts") or []), "created_at": _now(), "review_required": True, "filing_ready": False}
        entry["workspace_hash"] = _digest({key:value for key,value in entry.items() if key != "created_at"})
        with exclusive_file_lock(self.lock):
            state=self._load()
            if any(row.get("workspace_id") == workspace_id for row in state["workspaces"]): raise IntakeWorkbenchError("fee_waiver_workspace_id_already_exists", 409)
            state["workspaces"].append(entry); event={"event_id":f"fee_waiver_{uuid.uuid4().hex}","at":_now(),"action":"create_fee_waiver_workspace","workspace_id":workspace_id,"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True}; event["event_hash"]=_digest(event);state["ledger"].append(event);state["revision"]=int(state.get("revision") or 0)+1;self._save(state)
        return self._public(entry)

    def workspaces(self, workspace_id: str = "") -> dict[str, Any]:
        rows=[self._public(row) for row in self._load()["workspaces"]]
        if workspace_id:
            found=next((row for row in rows if row.get("workspace_id") == _id(workspace_id,"fee_waiver_workspace_id")),None)
            if found is None: raise IntakeWorkbenchError("fee_waiver_workspace_not_found",404)
            return {"workspace":found,"review_required":True,"local_only":True}
        return {"workspaces":rows,"review_required":True,"local_only":True}

    def source(self, workspace_id: str) -> dict[str, Any]:
        workspace=self.workspaces(workspace_id)["workspace"]
        return {"workspace_id":workspace["workspace_id"],"source":workspace["authority"],"review_required":True}
