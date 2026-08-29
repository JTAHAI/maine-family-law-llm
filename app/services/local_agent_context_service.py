"""Rehydrate local-model inputs; caller text and admission labels are never trusted."""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.services.authority_product_service import AuthorityProductService
from legal.agent_runtime.contracts import MAX_ITEM_CHARS, ContextSource, canonical_json, utc_now
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LocalAgentContextError(ValueError):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class LocalAgentSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["legal_authority", "private_record"]
    source_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:-]+$")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    start_offset: StrictInt = Field(ge=0)
    end_offset: StrictInt = Field(gt=0)
    build_id: str = Field(default="", max_length=64)
    build_manifest_sha256: str = Field(default="", max_length=64)
    record_token: str = Field(default="", max_length=64)


class LocalAgentContextService:
    def __init__(
        self, *, authority: AuthorityProductService, record_loader: Callable[[str], dict[str, Any]]
    ):
        self.authority = authority
        self.record_loader = record_loader

    def _authority_rows(self, ids: set[str]) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        try:
            active = self.authority._active_product(verify_all=True)
            manifest_hash = self.authority._sha256_file(active.manifest_path)
            matches: dict[str, list[dict[str, Any]]] = {source_id: [] for source_id in ids}
            for raw in self.authority._iter_active_parsed_rows(active):
                names = {str(raw.get("record_id") or ""), str(raw.get("source_id") or "")}
                for source_id in ids & names:
                    matches[source_id].append(raw)
            rows = {}
            for source_id, candidates in matches.items():
                if len(candidates) != 1:
                    continue  # An index ID shared by several sections is not an exact source.
                raw = candidates[0]
                text = str(raw.get("text") or raw.get("body") or raw.get("instructions") or "")
                rows[source_id] = {
                    "source_id": str(raw.get("record_id") or raw.get("source_id")),
                    "text": text,
                    "source_sha256": str(raw.get("source_hash") or ""),
                    "title": str(raw.get("title") or raw.get("citation") or source_id),
                    "source_class": str(
                        raw.get("source_class") or raw.get("authority_kind") or "unknown"
                    ),
                    "freshness_status": str(raw.get("freshness_status") or "unknown"),
                    "authority_status": "verified_immutable_source_not_current_law_determination",
                    "build_id": active.build_id,
                    "build_manifest_sha256": manifest_hash,
                }
            return rows
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise LocalAgentContextError("local_agent_authority_unavailable") from exc

    def references_from_cards(self, cards: list[dict[str, Any]]) -> list[LocalAgentSourceReference]:
        """Prepare exact selectors from host retrieval, without trusting its text as evidence."""
        candidates = []
        for card in cards[:24]:
            metadata = dict(card.get("metadata") or {})
            lane = str(metadata.get("source_lane") or "")
            if lane not in {"legal_authority", "private_record"}:
                continue
            candidates.append(
                (
                    card,
                    metadata,
                    lane,
                    str(
                        card.get("source_id")
                        or card.get("evidence_id")
                        or metadata.get("source_id")
                        or metadata.get("id")
                        or ""
                    ),
                )
            )
        try:
            authority_rows = self._authority_rows(
                {item[3] for item in candidates if item[2] == "legal_authority"}
            )
        except LocalAgentContextError:
            authority_rows = {}
        references = []
        for card, metadata, lane, source_id in candidates:
            token = str(
                metadata.get("record_open_token")
                or metadata.get("source_token")
                or card.get("source_token")
                or ""
            )
            try:
                row = (
                    self.record_loader(token)
                    if lane == "private_record"
                    else authority_rows.get(source_id)
                )
                if not row:
                    continue
                text = str(row["text"])
                excerpt = str(
                    card.get("snippet")
                    or card.get("text")
                    or metadata.get("text_excerpt")
                    or metadata.get("matched_text")
                    or ""
                )
                if not excerpt or len(excerpt) > MAX_ITEM_CHARS or "\x00" in excerpt:
                    continue
                start = text.find(excerpt)
                end = start + len(excerpt)
                if start < 0:
                    # Retrieval display may collapse whitespace. Map only a unique,
                    # whitespace-equivalent occurrence back to the original bytes;
                    # never fuzzy-match words, punctuation, or guessed OCR.
                    tokens = excerpt.split()
                    if not tokens:
                        continue
                    pattern = re.compile(r"\s+".join(re.escape(token) for token in tokens))
                    matches = pattern.finditer(text)
                    match = next(matches, None)
                    if match is None or next(matches, None) is not None:
                        continue
                    start, end = match.span()
                if end - start > MAX_ITEM_CHARS:
                    continue
                references.append(
                    LocalAgentSourceReference(
                        lane=lane,
                        source_id=row["source_id"],
                        source_sha256=row["source_sha256"],
                        text_sha256=text_digest(text),
                        start_offset=start,
                        end_offset=end,
                        build_id=row.get("build_id", ""),
                        build_manifest_sha256=row.get("build_manifest_sha256", ""),
                        record_token=token if lane == "private_record" else "",
                    )
                )
            except (LocalAgentContextError, ValueError, KeyError):
                continue
        return references

    def resolve(
        self, references: list[LocalAgentSourceReference]
    ) -> tuple[tuple[ContextSource, ...], list[dict[str, Any]]]:
        if not references or len(references) > 24:
            raise LocalAgentContextError("local_agent_source_references_required", 400)
        rows = self._authority_rows(
            {ref.source_id for ref in references if ref.lane == "legal_authority"}
        )
        sources, cards = [], []
        seen: set[tuple[str, str, str]] = set()
        for ref in references:
            if ref.lane == "private_record":
                if ref.build_id or ref.build_manifest_sha256 or not ref.record_token:
                    raise LocalAgentContextError("local_agent_record_reference_invalid")
                row = self.record_loader(ref.record_token)
            else:
                if ref.record_token:
                    raise LocalAgentContextError("local_agent_authority_reference_invalid")
                row = rows.get(ref.source_id)
                if (
                    not row
                    or ref.build_id != row["build_id"]
                    or ref.build_manifest_sha256 != row["build_manifest_sha256"]
                ):
                    raise LocalAgentContextError("local_agent_authority_generation_changed")
            if row["source_id"] != ref.source_id or row["source_sha256"] != ref.source_sha256:
                raise LocalAgentContextError("local_agent_source_identity_changed")
            text = str(row["text"])
            if text_digest(text) != ref.text_sha256:
                raise LocalAgentContextError("local_agent_source_text_changed")
            if (
                not 0 <= ref.start_offset < ref.end_offset <= len(text)
                or ref.end_offset - ref.start_offset > MAX_ITEM_CHARS
            ):
                raise LocalAgentContextError("local_agent_source_span_invalid")
            excerpt = text[ref.start_offset : ref.end_offset]
            if "\x00" in excerpt:
                raise LocalAgentContextError("local_agent_source_text_invalid")
            # Match ContextManifestBuilder's deduplication so entry indexes and
            # the exact-text cards shown in the approval dialog cannot diverge.
            key = (ref.lane, ref.source_id, text_digest(excerpt))
            if key in seen:
                continue
            seen.add(key)
            source = ContextSource(
                source_id=ref.source_id,
                lane=ref.lane,
                title=str(row.get("title") or ref.source_id),
                text=excerpt,
                locator=f"characters {ref.start_offset}-{ref.end_offset}",
                source_class=str(row.get("source_class") or "private_record"),
                authority_status=str(
                    row.get("authority_status") or "private_record_not_legal_authority"
                ),
                freshness_status=str(row.get("freshness_status") or "unknown"),
            )
            sources.append(source)
            cards.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "snippet": source.text,
                    "locator": source.locator,
                    "source_reference": ref.model_dump(),
                    "metadata": {
                        "source_lane": ref.lane,
                        "source_class": source.source_class,
                        "authority_status": source.authority_status,
                        "freshness_status": source.freshness_status,
                        "record_open_token": ref.record_token,
                        "source_hash": ref.source_sha256,
                    },
                    "review_required": True,
                }
            )
        if sum(len(source.text) for source in sources) > 80_000:
            raise LocalAgentContextError("local_agent_context_budget_exceeded")
        return tuple(sources), cards


class LocalAgentApprovalStore:
    """Bounded, single-use, process-local approvals; restart invalidates them."""

    def __init__(self, *, ttl_seconds: int = 300, max_entries: int = 256):
        self.ttl = ttl_seconds
        self.maximum = max_entries
        self.lock = threading.RLock()
        self.entries: dict[str, dict[str, Any]] = {}

    def issue(self, binding: dict[str, Any], manifest: dict[str, Any]) -> str:
        with self.lock:
            now = time.monotonic()
            self.entries = {key: row for key, row in self.entries.items() if row["expires"] > now}
            if len(self.entries) >= self.maximum:
                raise LocalAgentContextError("local_agent_preview_capacity_reached", 429)
            token = secrets.token_hex(32)
            self.entries[token] = {
                "expires": now + self.ttl,
                "binding_sha256": digest(binding),
                "manifest": deepcopy(manifest),
            }
            return token

    def consume(self, token: str, binding: dict[str, Any], manifest_sha256: str) -> dict[str, Any]:
        with self.lock:
            row = self.entries.get(token)
            if not row or row["expires"] <= time.monotonic():
                self.entries.pop(token, None)
                raise LocalAgentContextError("local_agent_approval_expired_or_used")
            if not secrets.compare_digest(row["binding_sha256"], digest(binding)):
                raise LocalAgentContextError("local_agent_approval_context_changed")
            if row["manifest"]["manifest_sha256"] != manifest_sha256:
                raise LocalAgentContextError("local_agent_approval_manifest_changed")
            self.entries.pop(token)
            return deepcopy(row["manifest"])


class LocalAgentAuditStore:
    """Encrypted, hash-linked, content-free receipts. Audit failure blocks dispatch/output."""

    def __init__(self, root: Path, *, encryption_key: str):
        self.root = Path(root) / "40_RUNTIME" / "local-agent"
        self.path = self.root / "audit.json.enc"
        self.lock_path = self.root / ".audit.lock"
        self.encryptor = LocalEnvelopeEncryptor(encryption_key)

    def record(
        self, action: str, *, scope: dict[str, str], binding_sha256: str, receipt_sha256: str = ""
    ) -> dict[str, Any]:
        try:
            with exclusive_file_lock(self.lock_path):
                owner = digest({"tenant_id": scope["tenant_id"], "matter_id": scope["matter_id"]})
                state = {"schema": "local_agent_audit_v1", "owner": owner, "events": []}
                if self.path.exists():
                    state = self.encryptor.decrypt_json(
                        strict_json_load_path(
                            self.path, max_bytes=4 * 1024 * 1024, require_object=True
                        )
                    )
                if state.get("schema") != "local_agent_audit_v1" or state.get("owner") != owner:
                    raise LocalAgentContextError("local_agent_audit_scope_mismatch", 403)
                previous = ""
                for event in state["events"]:
                    unhashed = {key: value for key, value in event.items() if key != "event_sha256"}
                    if event.get("previous_sha256") != previous or event.get(
                        "event_sha256"
                    ) != digest(unhashed):
                        raise LocalAgentContextError("local_agent_audit_integrity_failed")
                    previous = event["event_sha256"]
                if len(state["events"]) >= 4096:
                    raise LocalAgentContextError("local_agent_audit_capacity_reached")
                event = {
                    "event_id": secrets.token_hex(16),
                    "created_at": utc_now(),
                    "action": action,
                    "scope_sha256": digest(scope),
                    "binding_sha256": binding_sha256,
                    "receipt_sha256": receipt_sha256,
                    "previous_sha256": previous,
                    "review_required": True,
                }
                event["event_sha256"] = digest(event)
                state["events"].append(event)
                atomic_write_bytes(
                    self.path, canonical_json(self.encryptor.encrypt_json(state)), mode=0o600
                )
                return event
        except LocalAgentContextError:
            raise
        except Exception as exc:
            raise LocalAgentContextError("local_agent_audit_unavailable", 503) from exc
