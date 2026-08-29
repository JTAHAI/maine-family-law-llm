"""Encrypted, discardable local retrieval previews for typed intent.

These previews are not answers.  They hold a sanitized query and compact
source-card metadata only long enough for a user to inspect or discard them.
Nothing is transmitted beyond the supplied local retriever, and no preview can
be promoted to a legal or factual conclusion.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.prompt_injection import PromptInjectionScanner
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_GENERIC = frozenset({"a", "an", "and", "ask", "for", "help", "i", "me", "of", "please", "the", "to", "what"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any) -> str:
    output = str(value or "").strip().casefold()
    if not _ID.fullmatch(output):
        raise IntakeWorkbenchError("speculative_retrieval_id_invalid")
    return output


def _substantive(value: str) -> bool:
    tokens = {token.casefold() for token in re.findall(r"[a-z0-9'-]+", value) if len(token) > 1}
    return bool(tokens - _GENERIC)


class SpeculativeRetrievalStore:
    schema = "maine_family_law_llm.speculative_retrieval.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "speculative-retrieval"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )
        self.scanner = PromptInjectionScanner()

    @property
    def path(self) -> Path:
        return self.root / "previews.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".previews.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "previews": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=2 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("speculative_retrieval_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("speculative_retrieval_unavailable", 409)
        self._verify_events(state)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> None:
        prior = ""
        for event in state.get("events", []):
            copy = dict(event)
            actual = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != prior or actual != _digest(copy):
                raise IntakeWorkbenchError("speculative_retrieval_history_invalid", 409)
            prior = actual

    @staticmethod
    def _event(state: dict[str, Any], action: str, preview_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"spec_evt_{hashlib.sha256((action + preview_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "preview_id": preview_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _public(preview: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(preview.get(key))
            for key in (
                "preview_id", "status", "intent_lanes", "query_sha256", "candidate_sources",
                "created_at", "discarded_at", "blockers", "review_required", "answer_committed",
                "local_only", "network_used",
            )
        }

    @staticmethod
    def _candidate(raw: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(raw.get("metadata") or {})
        source_id = str(raw.get("source_id") or raw.get("citation") or "unknown")[:160]
        return {
            "source_id": source_id,
            "title": str(raw.get("title") or raw.get("citation") or source_id)[:300],
            "citation": str(raw.get("citation") or "")[:300],
            "locator": str(metadata.get("official_url") or metadata.get("source_url") or metadata.get("locator") or "")[:800],
            "source_class": str(metadata.get("source_class") or "")[:120],
            "freshness_status": str(metadata.get("freshness_status") or "unknown")[:120],
            "exact_reference_match": bool(raw.get("exact_reference_match", False)),
        }

    @staticmethod
    def _lanes(query: str) -> list[str]:
        value = query.casefold()
        lanes = ["official_authority"]
        if any(word in value for word in ("form", "fm-", "pa-", "cv-")):
            lanes.append("forms")
        if any(word in value for word in ("deadline", "hearing", "notice", "service")):
            lanes.append("procedure")
        return lanes

    def stage(self, payload: dict[str, Any], *, retriever: Callable[[str], list[dict[str, Any]]]) -> dict[str, Any]:
        preview_id = _id(payload.get("preview_id"))
        typed = " ".join(str(payload.get("typed_intent") or "").replace("\x00", " ").split())[:2_000]
        if not typed or not _substantive(typed):
            raise IntakeWorkbenchError("speculative_retrieval_substantive_intent_required")
        findings = self.scanner.scan_user_prompt(typed)
        sanitized = self.scanner.sanitize_user_prompt_for_retrieval(typed) if findings else typed
        blockers: list[str] = []
        candidates: list[dict[str, Any]] = []
        status = "preview_available_review_required"
        if not _substantive(sanitized):
            status = "preview_blocked_review_required"
            blockers.append("typed_intent_sanitized_to_no_substantive_query")
        else:
            try:
                candidates = [self._candidate(row) for row in retriever(sanitized)[:5] if isinstance(row, dict)]
            except Exception:
                status = "preview_unavailable_review_required"
                blockers.append("local_retrieval_unavailable")
        preview = {
            "preview_id": preview_id,
            "status": status,
            "intent_lanes": self._lanes(sanitized),
            "query_sha256": hashlib.sha256(sanitized.encode("utf-8")).hexdigest(),
            "candidate_sources": candidates,
            "created_at": _now(),
            "discarded_at": "",
            "blockers": blockers,
            "review_required": True,
            "answer_committed": False,
            "local_only": True,
            "network_used": False,
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            state["previews"][preview_id] = preview
            event = self._event(
                state,
                "speculative_retrieval_staged",
                preview_id,
                {"candidate_count": len(candidates), "prompt_sanitized": bool(findings), "status": status},
            )
            self._write(state)
        return {"preview": self._public(preview), "receipt": deepcopy(event)}

    def get(self, preview_id: str) -> dict[str, Any]:
        preview = self._load()["previews"].get(_id(preview_id))
        if not preview:
            raise IntakeWorkbenchError("speculative_retrieval_not_found", 404)
        return {"preview": self._public(preview)}

    def candidate(self, preview_id: str, source_id: str) -> dict[str, Any]:
        preview = self._load()["previews"].get(_id(preview_id))
        if not preview:
            raise IntakeWorkbenchError("speculative_retrieval_not_found", 404)
        candidate = next((row for row in preview.get("candidate_sources", []) if row.get("source_id") == str(source_id)[:160]), None)
        if not candidate:
            raise IntakeWorkbenchError("speculative_retrieval_source_not_found", 404)
        return {"candidate": deepcopy(candidate), "review_required": True, "answer_committed": False}

    def discard(self, preview_id: str) -> dict[str, Any]:
        safe_id = _id(preview_id)
        with exclusive_file_lock(self.lock):
            state = self._load()
            preview = state["previews"].get(safe_id)
            if not preview:
                raise IntakeWorkbenchError("speculative_retrieval_not_found", 404)
            preview.update({"status": "discarded_review_required", "discarded_at": _now(), "candidate_sources": []})
            event = self._event(state, "speculative_retrieval_discarded", safe_id, {})
            self._write(state)
        return {"preview": self._public(preview), "receipt": deepcopy(event)}
