"""Encrypted, source-bound prompt-prefix and retrieval cache.

Cache entries are never shared across matters.  Even public-authority entries
are encrypted at rest in the active matter so a caller cannot accidentally
write a private prompt prefix to a plaintext cache.  Each entry records only
source identifiers and content hashes for invalidation; source text itself is
stored only as the requested encrypted artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = frozenset({"prompt_prefix", "retrieval"})
_SCOPES = frozenset({"public_authority", "matter"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any, label: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"context_cache_{label}_invalid")
    return result


def _hash(value: Any, label: str) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError(f"context_cache_{label}_invalid")
    return result


class ContextCacheStore:
    schema = "maine_family_law_llm.context_cache.v1"

    def __init__(self, root: str | Path, *, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "context-cache"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "entries.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".entries.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "entries": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=4 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("context_cache_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("context_cache_unavailable", 409)
        self._verify_events(state)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _verify_events(state: dict[str, Any]) -> None:
        prior = ""
        for event in state.get("events", []):
            copy = dict(event)
            digest = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != prior or digest != _digest(copy):
                raise IntakeWorkbenchError("context_cache_history_invalid", 409)
            prior = digest

    @staticmethod
    def _event(state: dict[str, Any], action: str, cache_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {
            "event_id": f"cache_evt_{hashlib.sha256((action + cache_id + _now()).encode()).hexdigest()[:24]}",
            "at": _now(),
            "action": action,
            "cache_id": cache_id,
            "detail": deepcopy(detail),
            "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "",
            "review_required": True,
        }
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _public(entry: dict[str, Any], *, include_artifact: bool = False) -> dict[str, Any]:
        result = {
            key: deepcopy(entry.get(key))
            for key in (
                "cache_id", "kind", "scope", "source_refs", "status", "created_at", "invalidated_at",
                "invalidation_reason", "artifact_sha256", "review_required", "local_only", "network_used",
            )
        }
        if include_artifact:
            result["artifact"] = deepcopy(entry.get("artifact"))
        return result

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(event.get(key))
            for key in ("event_id", "at", "action", "cache_id", "detail", "review_required", "event_hash")
        }

    @staticmethod
    def _source_refs(value: Any, scope: str) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > 48:
            raise IntakeWorkbenchError("context_cache_source_refs_invalid")
        refs: list[dict[str, Any]] = []
        for raw in value:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("context_cache_source_ref_invalid")
            private = bool(raw.get("private_record", False))
            if scope == "public_authority" and private:
                raise IntakeWorkbenchError("context_cache_public_scope_private_source_refused", 409)
            source_token = str(raw.get("source_token") or "").strip().casefold()
            if source_token and not _HASH.fullmatch(source_token):
                raise IntakeWorkbenchError("context_cache_source_token_invalid")
            refs.append(
                {
                    "source_id": _id(raw.get("source_id"), "source_id"),
                    "content_sha256": _hash(raw.get("content_sha256"), "source_hash"),
                    "private_record": private,
                    "source_token": source_token,
                }
            )
        return refs

    def put(self, payload: dict[str, Any]) -> dict[str, Any]:
        cache_id = _id(payload.get("cache_id"), "id")
        kind = str(payload.get("kind") or "").strip().casefold()
        scope = str(payload.get("scope") or "").strip().casefold()
        if kind not in _KINDS or scope not in _SCOPES:
            raise IntakeWorkbenchError("context_cache_kind_or_scope_invalid")
        source_refs = self._source_refs(payload.get("source_refs"), scope)
        artifact = payload.get("artifact")
        if not isinstance(artifact, (dict, list, str)):
            raise IntakeWorkbenchError("context_cache_artifact_invalid")
        artifact_bytes = _canonical(artifact)
        if len(artifact_bytes) > 128_000:
            raise IntakeWorkbenchError("context_cache_artifact_too_large", 413)
        record = {
            "cache_id": cache_id,
            "kind": kind,
            "scope": scope,
            "source_refs": source_refs,
            "artifact": deepcopy(artifact),
            "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "status": "valid_review_required",
            "created_at": _now(),
            "invalidated_at": "",
            "invalidation_reason": "",
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }
        with exclusive_file_lock(self.lock):
            state = self._load()
            if cache_id in state["entries"]:
                raise IntakeWorkbenchError("context_cache_id_exists", 409)
            state["entries"][cache_id] = record
            event = self._event(
                state, "cache_entry_created", cache_id,
                {"kind": kind, "scope": scope, "source_count": len(source_refs)},
            )
            self._write(state)
        return {"entry": self._public(record), "receipt": self._public_event(event)}

    def get(self, cache_id: str) -> dict[str, Any]:
        entry = self._load()["entries"].get(_id(cache_id, "id"))
        if not entry:
            raise IntakeWorkbenchError("context_cache_not_found", 404)
        return {"entry": self._public(entry, include_artifact=True)}

    def source(self, cache_id: str, source_id: str) -> dict[str, Any]:
        entry = self._load()["entries"].get(_id(cache_id, "id"))
        if not entry:
            raise IntakeWorkbenchError("context_cache_not_found", 404)
        safe_source = _id(source_id, "source_id")
        ref = next((item for item in entry.get("source_refs", []) if item.get("source_id") == safe_source), None)
        if not ref:
            raise IntakeWorkbenchError("context_cache_source_not_found", 404)
        return {"source_ref": deepcopy(ref), "review_required": True}

    def invalidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        changes = payload.get("changes")
        if not isinstance(changes, list) or not changes or len(changes) > 96:
            raise IntakeWorkbenchError("context_cache_changes_invalid")
        current_hashes: dict[str, str] = {}
        for raw in changes:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("context_cache_change_invalid")
            source_id = _id(raw.get("source_id"), "source_id")
            hash_value = str(raw.get("content_sha256") or "").strip().casefold()
            if hash_value and not _HASH.fullmatch(hash_value):
                raise IntakeWorkbenchError("context_cache_source_hash_invalid")
            current_hashes[source_id] = hash_value
        invalidated: list[str] = []
        with exclusive_file_lock(self.lock):
            state = self._load()
            for cache_id, entry in state["entries"].items():
                changed = [
                    ref["source_id"]
                    for ref in entry.get("source_refs", [])
                    if ref["source_id"] in current_hashes
                    and current_hashes[ref["source_id"]] != ref["content_sha256"]
                ]
                if not changed or entry.get("status") == "invalidated_review_required":
                    continue
                entry.update(
                    {
                        "status": "invalidated_review_required",
                        "invalidated_at": _now(),
                        "invalidation_reason": "source_hash_changed_or_removed",
                    }
                )
                self._event(state, "cache_entry_invalidated", cache_id, {"source_ids": changed})
                invalidated.append(cache_id)
            self._write(state)
        return {
            "invalidated_cache_ids": invalidated,
            "status": "review_required",
            "local_only": True,
            "network_used": False,
        }

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            "schema_version": "context_cache_status_v1",
            "entries": [self._public(entry) for entry in state.get("entries", {}).values()],
            "recent_events": [self._public_event(event) for event in state.get("events", [])[-12:]][::-1],
            "review_required": True,
            "local_only": True,
            "network_used": False,
        }
