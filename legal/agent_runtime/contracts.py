"""Contracts for the optional local-agent runtime.

The contracts are intentionally provider-neutral and data-minimizing.  They bind
an exact, visible context manifest to a generated answer without treating model
output as legal authority, evidence, or filing-ready work product.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any, Iterable

SCHEMA_VERSION = "local_agent_contract_v1"
CONTEXT_MANIFEST_SCHEMA = "local_agent_context_manifest_v1"
PROVENANCE_SCHEMA = "local_agent_provenance_receipt_v1"
ALLOWED_LANES = {"legal_authority", "private_record", "host_baseline", "tool_result"}
MAX_CONTEXT_ITEMS = 24
MAX_CONTEXT_CHARS = 80_000
MAX_ITEM_CHARS = 20_000
MAX_QUESTION_CHARS = 20_000
MAX_TITLE_CHARS = 300
MAX_LOCATOR_CHARS = 500
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def safe_identifier(value: str, *, fallback: str) -> str:
    cleaned = _SAFE_ID_RE.sub("-", str(value or "").strip()).strip("-.")
    return (cleaned or fallback)[:160]


@dataclass(frozen=True)
class ContextSource:
    source_id: str
    lane: str
    title: str
    text: str
    locator: str | None = None
    source_class: str | None = None
    authority_status: str | None = None
    freshness_status: str | None = None
    instruction_like_text_detected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "ContextSource":
        lane = str(self.lane or "").strip().lower()
        if lane not in ALLOWED_LANES:
            raise ValueError(f"unsupported_context_lane:{lane or 'missing'}")
        text = str(self.text or "").replace("\x00", "")
        if not text.strip():
            raise ValueError("context_text_required")
        if len(text) > MAX_ITEM_CHARS:
            text = text[:MAX_ITEM_CHARS]
        title = " ".join(str(self.title or "Source").replace("\x00", " ").split())[:MAX_TITLE_CHARS]
        locator = " ".join(str(self.locator or "").replace("\x00", " ").split())[:MAX_LOCATOR_CHARS] or None
        return ContextSource(
            source_id=safe_identifier(self.source_id, fallback="source"),
            lane=lane,
            title=title or "Source",
            text=text,
            locator=locator,
            source_class=(str(self.source_class or "")[:120] or None),
            authority_status=(str(self.authority_status or "")[:120] or None),
            freshness_status=(str(self.freshness_status or "")[:120] or None),
            instruction_like_text_detected=bool(self.instruction_like_text_detected),
            metadata=dict(self.metadata or {}),
        )


@dataclass(frozen=True)
class ContextManifestEntry:
    index: int
    source_id: str
    lane: str
    title: str
    locator: str | None
    source_class: str | None
    authority_status: str | None
    freshness_status: str | None
    char_count: int
    content_sha256: str
    instruction_like_text_detected: bool
    preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "source_id": self.source_id,
            "lane": self.lane,
            "title": self.title,
            "locator": self.locator,
            "source_class": self.source_class,
            "authority_status": self.authority_status,
            "freshness_status": self.freshness_status,
            "char_count": self.char_count,
            "content_sha256": self.content_sha256,
            "instruction_like_text_detected": self.instruction_like_text_detected,
            "preview": self.preview,
        }


@dataclass(frozen=True)
class ContextManifest:
    run_id: str
    question_sha256: str
    created_at: str
    entries: tuple[ContextManifestEntry, ...]
    total_chars: int
    lane_counts: dict[str, int]
    exact_context_sha256: str
    manifest_sha256: str
    truncated: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONTEXT_MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "question_sha256": self.question_sha256,
            "created_at": self.created_at,
            "entries": [entry.to_dict() for entry in self.entries],
            "entry_count": len(self.entries),
            "total_chars": self.total_chars,
            "lane_counts": dict(self.lane_counts),
            "exact_context_sha256": self.exact_context_sha256,
            "manifest_sha256": self.manifest_sha256,
            "truncated": self.truncated,
            "warnings": list(self.warnings),
            "review_required": True,
            "transmission_scope": "loopback_local_model_only",
        }


class ContextManifestBuilder:
    """Build a stable manifest and the exact bounded source packet.

    Duplicate source bytes are represented once.  The original source text is
    not modified by this builder; any quarantine transformation is applied to a
    separate prompt-only copy by the runtime.
    """

    def __init__(self, *, max_items: int = MAX_CONTEXT_ITEMS, max_chars: int = MAX_CONTEXT_CHARS):
        self.max_items = max(1, min(int(max_items), MAX_CONTEXT_ITEMS))
        self.max_chars = max(1_000, min(int(max_chars), MAX_CONTEXT_CHARS))

    def build(
        self,
        *,
        question: str,
        sources: Iterable[ContextSource],
        run_id: str,
        created_at: str | None = None,
    ) -> tuple[ContextManifest, tuple[ContextSource, ...]]:
        question = str(question or "").replace("\x00", "").strip()
        if not question:
            raise ValueError("question_required")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValueError("question_too_large")

        selected: list[ContextSource] = []
        seen: set[tuple[str, str, str]] = set()
        total_chars = 0
        warnings: list[str] = []
        truncated = False
        for raw in sources:
            normalized = raw.normalized()
            digest = sha256_text(normalized.text)
            dedupe_key = (normalized.lane, normalized.source_id, digest)
            if dedupe_key in seen:
                continue
            if len(selected) >= self.max_items or total_chars + len(normalized.text) > self.max_chars:
                truncated = True
                warnings.append("context_budget_truncated")
                break
            seen.add(dedupe_key)
            selected.append(normalized)
            total_chars += len(normalized.text)

        if not selected:
            raise ValueError("context_sources_required")

        entries: list[ContextManifestEntry] = []
        lane_counts: dict[str, int] = {}
        exact_parts: list[dict[str, Any]] = []
        for index, source in enumerate(selected, start=1):
            digest = sha256_text(source.text)
            lane_counts[source.lane] = lane_counts.get(source.lane, 0) + 1
            preview = " ".join(source.text.split())
            if len(preview) > 220:
                preview = preview[:217].rstrip() + "..."
            entry = ContextManifestEntry(
                index=index,
                source_id=source.source_id,
                lane=source.lane,
                title=source.title,
                locator=source.locator,
                source_class=source.source_class,
                authority_status=source.authority_status,
                freshness_status=source.freshness_status,
                char_count=len(source.text),
                content_sha256=digest,
                instruction_like_text_detected=source.instruction_like_text_detected,
                preview=preview,
            )
            entries.append(entry)
            exact_parts.append(
                {
                    "index": index,
                    "source_id": source.source_id,
                    "lane": source.lane,
                    "content_sha256": digest,
                    "text": source.text,
                }
            )

        exact_context_sha256 = sha256(canonical_json(exact_parts)).hexdigest()
        base = {
            "schema_version": CONTEXT_MANIFEST_SCHEMA,
            "run_id": safe_identifier(run_id, fallback="run"),
            "question_sha256": sha256_text(question),
            "created_at": created_at or utc_now(),
            "entries": [entry.to_dict() for entry in entries],
            "total_chars": total_chars,
            "lane_counts": lane_counts,
            "exact_context_sha256": exact_context_sha256,
            "truncated": truncated,
            "warnings": warnings,
        }
        manifest_sha256 = sha256(canonical_json(base)).hexdigest()
        manifest = ContextManifest(
            run_id=base["run_id"],
            question_sha256=base["question_sha256"],
            created_at=base["created_at"],
            entries=tuple(entries),
            total_chars=total_chars,
            lane_counts=lane_counts,
            exact_context_sha256=exact_context_sha256,
            manifest_sha256=manifest_sha256,
            truncated=truncated,
            warnings=tuple(warnings),
        )
        return manifest, tuple(selected)


@dataclass(frozen=True)
class ProvenanceReceipt:
    run_id: str
    question_sha256: str
    context_manifest_sha256: str
    exact_context_sha256: str
    answer_sha256: str
    provider_id: str
    model_id: str
    endpoint_class: str
    status: str
    citation_refs: tuple[int, ...]
    tool_receipt_hashes: tuple[str, ...]
    retrieval_diagnostics_sha256: str
    created_at: str
    receipt_sha256: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        question: str,
        manifest: ContextManifest,
        answer: str,
        provider_id: str,
        model_id: str,
        endpoint_class: str,
        status: str,
        citation_refs: Iterable[int] = (),
        tool_receipt_hashes: Iterable[str] = (),
        retrieval_diagnostics: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> "ProvenanceReceipt":
        payload = {
            "schema_version": PROVENANCE_SCHEMA,
            "run_id": safe_identifier(run_id, fallback="run"),
            "question_sha256": sha256_text(question),
            "context_manifest_sha256": manifest.manifest_sha256,
            "exact_context_sha256": manifest.exact_context_sha256,
            "answer_sha256": sha256_text(answer),
            "provider_id": safe_identifier(provider_id, fallback="local"),
            "model_id": str(model_id or "unknown")[:200],
            "endpoint_class": str(endpoint_class or "loopback")[:100],
            "status": str(status or "review_required")[:100],
            "citation_refs": sorted({int(value) for value in citation_refs if int(value) > 0}),
            "tool_receipt_hashes": sorted({str(value) for value in tool_receipt_hashes if value}),
            "retrieval_diagnostics_sha256": sha256(canonical_json(retrieval_diagnostics or {})).hexdigest(),
            "created_at": created_at or utc_now(),
        }
        receipt_sha256 = sha256(canonical_json(payload)).hexdigest()
        return cls(receipt_sha256=receipt_sha256, **{key: value for key, value in payload.items() if key != "schema_version"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROVENANCE_SCHEMA,
            "run_id": self.run_id,
            "question_sha256": self.question_sha256,
            "context_manifest_sha256": self.context_manifest_sha256,
            "exact_context_sha256": self.exact_context_sha256,
            "answer_sha256": self.answer_sha256,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "endpoint_class": self.endpoint_class,
            "status": self.status,
            "citation_refs": list(self.citation_refs),
            "tool_receipt_hashes": list(self.tool_receipt_hashes),
            "retrieval_diagnostics_sha256": self.retrieval_diagnostics_sha256,
            "created_at": self.created_at,
            "receipt_sha256": self.receipt_sha256,
            "review_required": True,
            "legal_authority": False,
            "evidence": False,
        }
