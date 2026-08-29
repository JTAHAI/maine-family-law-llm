"""Encrypted, matter-scoped structured review-comment threads.

Comments are review aids, not edits to a record, source, claim, draft, or
artifact.  Their target is immutable and hash-bound at creation; replies and
resolution entries append to an encrypted ledger rather than changing prior
comments or silently changing the underlying work product.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
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
_TARGET_KINDS = frozenset({"record_span", "source_span", "claim", "draft_text", "artifact"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip().casefold()
    if not _ID.fullmatch(text):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return text


def _hash_value(value: Any, field: str) -> str:
    text = str(value or "").strip().casefold()
    if not _HASH.fullmatch(text):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return text


def _text(value: Any, field: str, maximum: int = 4_000) -> str:
    text = str(value or "").strip()
    if not text:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(text) > maximum:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return text


def _offset(value: Any, field: str) -> int:
    if type(value) is not int or value < 0 or value > 50_000_000:
        raise IntakeWorkbenchError(f"{field}_invalid")
    return value


def _span(payload: dict[str, Any], prefix: str) -> dict[str, int]:
    start = _offset(payload.get(f"{prefix}_start"), f"{prefix}_start")
    end = _offset(payload.get(f"{prefix}_end"), f"{prefix}_end")
    if end <= start:
        raise IntakeWorkbenchError(f"{prefix}_range_invalid")
    return {"start": start, "end": end}


def _target(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("target_kind") or "").strip().casefold()
    if kind not in _TARGET_KINDS:
        raise IntakeWorkbenchError("structured_comment_target_kind_invalid")
    target: dict[str, Any] = {"kind": kind}
    if kind == "record_span":
        target.update({"record_id": _id(payload.get("record_id"), "record_id"), "source_hash": _hash_value(payload.get("source_hash"), "source_hash"), "span": _span(payload, "character")})
        target["source_drill_down"] = {"route": f"/api/records/{target['record_id']}/integrity", "kind": "active_matter_record", "exact_span": target["span"], "review_required": True}
    elif kind == "source_span":
        source_id = str(payload.get("source_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{3,240}", source_id):
            raise IntakeWorkbenchError("source_id_invalid")
        target.update({"source_id": source_id, "source_hash": _hash_value(payload.get("source_hash"), "source_hash"), "span": _span(payload, "character")})
        target["source_drill_down"] = {"route": "/api/authority/search", "kind": "official_source", "source_id": source_id, "exact_span": target["span"], "review_required": True}
    elif kind == "claim":
        target.update({"claim_id": _id(payload.get("claim_id"), "claim_id"), "claim_hash": _hash_value(payload.get("claim_hash"), "claim_hash")})
        target["source_drill_down"] = {"kind": "claim_review", "claim_id": target["claim_id"], "claim_hash": target["claim_hash"], "review_required": True}
    elif kind == "draft_text":
        target.update({"document_id": _id(payload.get("document_id"), "document_id"), "revision_hash": _hash_value(payload.get("revision_hash"), "revision_hash"), "span": _span(payload, "character")})
        target["source_drill_down"] = {"route": f"/api/document-workspace/documents/{target['document_id']}", "kind": "draft_revision", "revision_hash": target["revision_hash"], "exact_span": target["span"], "review_required": True}
    else:
        target.update({"artifact_id": _id(payload.get("artifact_id"), "artifact_id"), "artifact_hash": _hash_value(payload.get("artifact_hash"), "artifact_hash")})
        target["source_drill_down"] = {"kind": "review_artifact", "artifact_id": target["artifact_id"], "artifact_hash": target["artifact_hash"], "review_required": True}
    return target


class StructuredCommentThreadStore:
    schema = "maine_family_law_llm.structured_comment_threads.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "45_STRUCTURED_COMMENT_THREADS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("structured_comment_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode("utf-8")).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "threads.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".threads.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "threads": [], "history": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=12 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("structured_comment_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope or not isinstance(value.get("threads"), list) or not isinstance(value.get("history"), list):
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode("utf-8"), mode=0o600)

    def _mutate(self, action: str, identifiers: list[str], operation: Callable[[dict[str, Any]], Any]) -> Any:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = operation(value)
            event = {"event_id": f"structured_comment_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": identifiers, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    @staticmethod
    def _thread(value: dict[str, Any], thread_id: str) -> dict[str, Any]:
        for row in value["threads"]:
            if row.get("thread_id") == thread_id:
                return row
        raise IntakeWorkbenchError("structured_comment_thread_not_found", 404)

    @staticmethod
    def _public_thread(thread: dict[str, Any], *, include_bodies: bool) -> dict[str, Any]:
        result = deepcopy(thread)
        if not include_bodies:
            for comment in result.get("comments", []):
                comment.pop("body", None)
                comment.pop("resolution_note", None)
        result["review_required"] = True
        result["local_only"] = True
        result["automatic_merge"] = False
        return result

    def inventory(self) -> dict[str, Any]:
        value = self._load()
        return {
            "schema": self.schema,
            "threads": [self._public_thread(row, include_bodies=False) for row in value["threads"]],
            "revision": value["revision"],
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "local_only": True,
            "external_messaging": False,
            "automatic_merge": False,
            "private_comment_bodies_in_inventory": False,
        }

    def create_thread(self, payload: dict[str, Any]) -> dict[str, Any]:
        thread_id = _id(payload.get("thread_id"), "thread_id")
        author = _id(payload.get("author_safe_id"), "author_safe_id")
        target = _target(payload)
        opening = _text(payload.get("body"), "structured_comment_body")

        def operation(value: dict[str, Any]) -> dict[str, Any]:
            if any(row.get("thread_id") == thread_id for row in value["threads"]):
                raise IntakeWorkbenchError("duplicate_structured_comment_thread_id", 409)
            comment = {"comment_id": f"opening_{thread_id}", "parent_comment_id": None, "author_safe_id": author, "body": opening, "created_at": _now(), "review_required": True}
            comment["comment_hash"] = _hash({**comment, "target_hash": _hash(target)})
            thread = {"thread_id": thread_id, "target": target, "target_hash": _hash(target), "state": "open", "comments": [comment], "created_at": _now(), "review_required": True}
            thread["thread_hash"] = _hash(thread)
            value["threads"].append(thread)
            return deepcopy(thread)

        return self._public_thread(self._mutate("structured_comment_thread_created", [thread_id], operation), include_bodies=True)

    def add_comment(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        thread_key = _id(thread_id, "thread_id")
        comment_id = _id(payload.get("comment_id"), "comment_id")
        author = _id(payload.get("author_safe_id"), "author_safe_id")
        body = _text(payload.get("body"), "structured_comment_body")
        parent = payload.get("parent_comment_id")
        parent_id = _id(parent, "parent_comment_id") if parent else None

        def operation(value: dict[str, Any]) -> dict[str, Any]:
            thread = self._thread(value, thread_key)
            if thread["state"] != "open":
                raise IntakeWorkbenchError("structured_comment_thread_resolved", 409)
            if any(row.get("comment_id") == comment_id for row in thread["comments"]):
                raise IntakeWorkbenchError("duplicate_structured_comment_id", 409)
            if parent_id and not any(row.get("comment_id") == parent_id for row in thread["comments"]):
                raise IntakeWorkbenchError("structured_comment_parent_not_found", 404)
            comment = {"comment_id": comment_id, "parent_comment_id": parent_id, "author_safe_id": author, "body": body, "created_at": _now(), "review_required": True}
            comment["comment_hash"] = _hash({**comment, "target_hash": thread["target_hash"]})
            thread["comments"].append(comment)
            thread["thread_hash"] = _hash({key: value for key, value in thread.items() if key != "thread_hash"})
            return deepcopy(thread)

        return self._public_thread(self._mutate("structured_comment_added", [thread_key, comment_id], operation), include_bodies=True)

    def resolve(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        thread_key = _id(thread_id, "thread_id")
        resolver = _id(payload.get("resolver_safe_id"), "resolver_safe_id")
        note = _text(payload.get("resolution_note"), "structured_comment_resolution_note")

        def operation(value: dict[str, Any]) -> dict[str, Any]:
            thread = self._thread(value, thread_key)
            if thread["state"] != "open":
                raise IntakeWorkbenchError("structured_comment_thread_not_open", 409)
            thread["state"] = "resolved_review_required"
            thread["resolution"] = {"resolver_safe_id": resolver, "resolution_note": note, "resolved_at": _now(), "not_a_legal_or_factual_determination": True, "review_required": True}
            thread["thread_hash"] = _hash({key: value for key, value in thread.items() if key != "thread_hash"})
            return deepcopy(thread)

        return self._public_thread(self._mutate("structured_comment_thread_resolved", [thread_key], operation), include_bodies=True)

    def get(self, thread_id: str) -> dict[str, Any]:
        return self._public_thread(self._thread(self._load(), _id(thread_id, "thread_id")), include_bodies=True)
