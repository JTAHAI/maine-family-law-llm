from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Callable

from legal.review.review_ledger import build_fact_evidence_report
from legal.verifiers import LegalOutputVerifier, QuoteSpanVerifier, SourceAuthorityIndex
from legal.verifiers.source_cards import SourceCardStore

from .schemas import canonical_json, safe_identifier, utc_now

MAX_TOOL_CALLS = 12
MAX_ARGS_BYTES = 16 * 1024
MAX_RESULT_BYTES = 128 * 1024
MAX_PREVIEW_CHARS = 500


@dataclass(frozen=True)
class DeliberationToolDefinition:
    name: str
    lane: str
    capability: str
    description: str
    requires_matter_scope: bool = False
    max_calls_per_run: int = 3
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliberationToolToken:
    token_id: str
    run_id: str
    matter_id: str
    worker_id: str
    tool_name: str
    capability: str
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class DeliberationToolCallAudit:
    call_id: str
    run_id: str
    worker_id: str
    tool_name: str
    validated_argument_hash: str
    policy_result: str
    returned_source_ids: list[str]
    duration_ms: int
    status: str
    created_at: str
    token_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "run_id": self.run_id,
            "worker_id": self.worker_id,
            "tool_name": self.tool_name,
            "validated_argument_hash": self.validated_argument_hash,
            "policy_result": self.policy_result,
            "returned_source_ids": list(self.returned_source_ids),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "created_at": self.created_at,
            "token_id": self.token_id,
        }


@dataclass
class DeliberationContext:
    run_id: str
    matter_id: str
    question: str
    source_texts: dict[str, str]
    source_metadata: dict[str, dict[str, Any]]
    record_texts: dict[str, str]
    record_metadata: dict[str, dict[str, Any]]
    tool_call_limit: int
    allowed_tools: set[str]
    cancellation_state: str = "active"
    source_cards: SourceCardStore = field(default_factory=SourceCardStore)
    authority_index: SourceAuthorityIndex = field(default_factory=SourceAuthorityIndex)

    def is_cancelled(self) -> bool:
        return self.cancellation_state != "active"


_DEFAULT_TOOL_DEFINITIONS = (
    DeliberationToolDefinition("authority.search", "legal_authority", "read_search", "Search approved Maine authority."),
    DeliberationToolDefinition("authority.get_span", "legal_authority", "read_span", "Return one bounded authority span."),
    DeliberationToolDefinition("authority.verify_citation", "verifier", "verify", "Resolve one citation."),
    DeliberationToolDefinition("authority.verify_quote", "verifier", "verify", "Verify a quote against a source span."),
    DeliberationToolDefinition("records.search", "private_record", "read_search", "Search the active matter.", requires_matter_scope=True),
    DeliberationToolDefinition("records.get_slice", "private_record", "read_span", "Return one bounded record slice.", requires_matter_scope=True),
    DeliberationToolDefinition("records.get_metadata", "private_record", "read_metadata", "Return record metadata.", requires_matter_scope=True),
    DeliberationToolDefinition("evidence.map_claim", "evidence", "analyze", "Map a claim to selected records.", requires_matter_scope=True),
    DeliberationToolDefinition("evidence.timeline_slice", "evidence", "analyze", "Build a bounded timeline slice.", requires_matter_scope=True),
    DeliberationToolDefinition("verification.check_claims", "verifier", "verify", "Run deterministic support checks."),
    DeliberationToolDefinition("review.request_human", "review", "handoff", "Create a human review request."),
)


class DeliberationToolBroker:
    def __init__(self, definitions: tuple[DeliberationToolDefinition, ...] = _DEFAULT_TOOL_DEFINITIONS) -> None:
        self.definitions = {definition.name: definition for definition in definitions}
        self.handlers: dict[str, Callable[[dict[str, Any], DeliberationContext], Any]] = {}
        self.tokens: dict[str, DeliberationToolToken] = {}
        self.call_counts: dict[tuple[str, str], int] = {}
        self.audit_log: list[DeliberationToolCallAudit] = []
        self._register_builtin_handlers()

    def _register_builtin_handlers(self) -> None:
        self.register("authority.search", self._handle_authority_search)
        self.register("authority.get_span", self._handle_authority_get_span)
        self.register("authority.verify_citation", self._handle_authority_verify_citation)
        self.register("authority.verify_quote", self._handle_authority_verify_quote)
        self.register("records.search", self._handle_records_search)
        self.register("records.get_slice", self._handle_records_get_slice)
        self.register("records.get_metadata", self._handle_records_get_metadata)
        self.register("evidence.map_claim", self._handle_evidence_map_claim)
        self.register("evidence.timeline_slice", self._handle_evidence_timeline_slice)
        self.register("verification.check_claims", self._handle_verification_check_claims)
        self.register("review.request_human", self._handle_review_request_human)

    def register(self, tool_name: str, handler: Callable[[dict[str, Any], DeliberationContext], Any]) -> None:
        if tool_name not in self.definitions:
            raise KeyError(f"tool_not_allowlisted:{tool_name}")
        self.handlers[tool_name] = handler

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "lane": definition.lane,
                "capability": definition.capability,
                "description": definition.description,
                "requires_matter_scope": definition.requires_matter_scope,
                "max_calls_per_run": definition.max_calls_per_run,
                "read_only": True,
            }
            for definition in self.definitions.values()
        ]

    def issue_token(self, *, run_id: str, matter_id: str, worker_id: str, tool_name: str) -> DeliberationToolToken:
        definition = self.definitions.get(tool_name)
        if definition is None:
            raise KeyError(f"tool_not_allowlisted:{tool_name}")
        token_id = secrets.token_hex(16)
        token = DeliberationToolToken(
            token_id=token_id,
            run_id=safe_identifier(run_id, fallback="run"),
            matter_id=safe_identifier(matter_id, fallback="matter"),
            worker_id=safe_identifier(worker_id, fallback="worker"),
            tool_name=tool_name,
            capability=definition.capability,
            created_at=utc_now(),
            expires_at=utc_now(),
        )
        self.tokens[token_id] = token
        return token

    def revoke_run_tokens(self, run_id: str) -> None:
        run_id = safe_identifier(run_id, fallback="run")
        self.tokens = {token_id: token for token_id, token in self.tokens.items() if token.run_id != run_id}

    def invoke(
        self,
        *,
        token_id: str,
        tool_name: str,
        payload: dict[str, Any],
        context: DeliberationContext,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        definition = self.definitions.get(tool_name)
        token = self.tokens.get(token_id)
        if definition is None:
            raise KeyError(f"tool_not_allowlisted:{tool_name}")
        if token is None:
            raise PermissionError("stale_tool_token")
        if token.tool_name != tool_name:
            raise PermissionError("tool_token_mismatch")
        if token.run_id != context.run_id:
            raise PermissionError("cross_run_tool_token")
        if token.matter_id != context.matter_id:
            raise PermissionError("cross_matter_tool_token")
        if context.is_cancelled():
            raise PermissionError("run_cancelled")
        if tool_name not in context.allowed_tools:
            raise PermissionError(f"tool_not_permitted:{tool_name}")
        per_tool_key = (context.run_id, tool_name)
        self.call_counts[per_tool_key] = self.call_counts.get(per_tool_key, 0) + 1
        if self.call_counts[per_tool_key] > definition.max_calls_per_run:
            raise ValueError(f"tool_call_limit_exceeded:{tool_name}")
        if len(self.audit_log) >= max(1, context.tool_call_limit):
            raise ValueError("tool_call_budget_exhausted")
        if definition.requires_matter_scope and context.matter_id == "unknown":
            raise PermissionError(f"tool_matter_scope_required:{tool_name}")
        handler = self.handlers.get(tool_name)
        if handler is None:
            raise RuntimeError(f"tool_handler_missing:{tool_name}")

        validated_args = dict(payload or {})
        args_bytes = canonical_json(validated_args)
        if len(args_bytes) > MAX_ARGS_BYTES:
            raise ValueError("tool_arguments_too_large")
        result = handler(validated_args, context)
        result = self._sanitize_result(result)
        result_bytes = canonical_json(result)
        if len(result_bytes) > MAX_RESULT_BYTES:
            raise ValueError("tool_result_too_large")
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        audit = DeliberationToolCallAudit(
            call_id=safe_identifier(f"{context.run_id}:{token.token_id}:{len(self.audit_log) + 1}", fallback="call"),
            run_id=context.run_id,
            worker_id=token.worker_id,
            tool_name=tool_name,
            validated_argument_hash=sha256(args_bytes).hexdigest(),
            policy_result="allowed",
            returned_source_ids=sorted({str(item) for item in result.get("returned_source_ids", []) if str(item).strip()}),
            duration_ms=duration_ms,
            status="completed",
            created_at=utc_now(),
            token_id=token.token_id,
        )
        self.audit_log.append(audit)
        result["tool_audit"] = audit.as_dict()
        result["review_required"] = True
        result["read_only"] = True
        result["bound_run_id"] = context.run_id
        return result

    def _sanitize_result(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"status": "unsupported_result_shape", "result": str(payload)[:MAX_PREVIEW_CHARS]}
        banned_keys = {
            "path",
            "paths",
            "file",
            "files",
            "url",
            "urls",
            "source_url_or_path",
            "snapshot_path",
            "manifest_path",
            "output_path",
            "absolute_path",
        }
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if key in banned_keys or key.endswith("_path"):
                continue
            if isinstance(value, str) and len(value) > MAX_PREVIEW_CHARS:
                sanitized[key] = value[: MAX_PREVIEW_CHARS - 3] + "..."
            elif isinstance(value, list):
                sanitized[key] = [self._trim(item) for item in value][:50]
            else:
                sanitized[key] = self._trim(value)
        return sanitized

    def _trim(self, value: Any) -> Any:
        if isinstance(value, str):
            return value[:MAX_PREVIEW_CHARS]
        if isinstance(value, dict):
            return {key: self._trim(item) for key, item in value.items() if key not in {"path", "url", "source_url_or_path"}}
        return value

    def _handle_authority_search(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip().casefold()
        rows: list[dict[str, Any]] = []
        for source_id, metadata in context.source_metadata.items():
            text = context.source_texts.get(source_id, "")
            title = str(metadata.get("title") or metadata.get("source_id") or source_id)
            haystack = f"{title}\n{text}\n{metadata.get('citation') or ''}".casefold()
            if query and query not in haystack:
                continue
            rows.append(
                {
                    "source_id": source_id,
                    "title": title,
                    "citation": metadata.get("citation"),
                    "source_class": metadata.get("source_class"),
                    "authority_status": metadata.get("authority_status"),
                    "freshness_status": metadata.get("freshness_status"),
                    "snippet": text[:240],
                }
            )
        return {"status": "pass", "matches": rows[:20], "returned_source_ids": [row["source_id"] for row in rows[:20]]}

    def _handle_authority_get_span(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        source_id = str(payload.get("source_id") or "").strip()
        text = context.source_texts.get(source_id, "")
        if not text:
            return {"status": "not_found", "source_id": source_id, "returned_source_ids": []}
        start = max(0, int(payload.get("start") or 0))
        end = int(payload.get("end") or min(len(text), start + 300))
        end = max(start, min(len(text), end))
        return {
            "status": "pass",
            "source_id": source_id,
            "start_offset": start,
            "end_offset": end,
            "span_text": text[start:end],
            "returned_source_ids": [source_id],
        }

    def _handle_authority_verify_citation(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        citation = str(payload.get("citation") or "").strip()
        source_id = str(payload.get("source_id") or "").strip() or None
        verifier = LegalOutputVerifier(context.authority_index)
        report = verifier.verify_output(text=citation, source_texts=context.source_texts, source_metadata=context.source_metadata, auto_extract_claims=False, auto_extract_quotes=False)
        citation_rows = [row for row in report.get("citations") or [] if citation.casefold() in str(row.get("citation", {}).get("raw") or row.get("citation", {}).get("normalized") or "").casefold()]
        status = citation_rows[0]["status"] if citation_rows else "unknown"
        return {
            "status": status,
            "citation": citation,
            "source_id": source_id,
            "verification_report": report,
            "returned_source_ids": [row.get("source_id") for row in citation_rows if row.get("source_id")],
        }

    def _handle_authority_verify_quote(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        source_id = str(payload.get("source_id") or "").strip()
        source_text = context.source_texts.get(source_id, "")
        quoted_text = str(payload.get("quoted_text") or "").strip()
        verification = QuoteSpanVerifier().verify(source_text, quoted_text)
        verification["source_id"] = source_id
        verification["returned_source_ids"] = [source_id] if source_id else []
        return verification

    def _handle_records_search(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip().casefold()
        rows: list[dict[str, Any]] = []
        for record_id, text in context.record_texts.items():
            metadata = context.record_metadata.get(record_id, {})
            haystack = f"{record_id}\n{metadata.get('title') or ''}\n{text}".casefold()
            if query and query not in haystack:
                continue
            rows.append(
                {
                    "record_id": record_id,
                    "title": metadata.get("title") or record_id,
                    "record_class": metadata.get("record_class") or metadata.get("source_class") or "record",
                    "record_status": metadata.get("privacy_status") or "unknown",
                    "snippet": text[:240],
                }
            )
        return {"status": "pass", "matches": rows[:20], "returned_source_ids": [row["record_id"] for row in rows[:20]]}

    def _handle_records_get_slice(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        record_id = str(payload.get("record_id") or "").strip()
        text = context.record_texts.get(record_id, "")
        if not text:
            return {"status": "not_found", "record_id": record_id, "returned_source_ids": []}
        start = max(0, int(payload.get("start") or 0))
        end = int(payload.get("end") or min(len(text), start + 300))
        end = max(start, min(len(text), end))
        return {
            "status": "pass",
            "record_id": record_id,
            "start_offset": start,
            "end_offset": end,
            "slice_text": text[start:end],
            "returned_source_ids": [record_id],
        }

    def _handle_records_get_metadata(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        record_id = str(payload.get("record_id") or "").strip()
        metadata = context.record_metadata.get(record_id, {})
        if not metadata:
            return {"status": "not_found", "record_id": record_id, "returned_source_ids": []}
        return {"status": "pass", "record_id": record_id, "metadata": dict(metadata), "returned_source_ids": [record_id]}

    def _handle_evidence_map_claim(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        claim = str(payload.get("claim") or "").strip()
        record_ids = [str(value).strip() for value in payload.get("record_ids") or [] if str(value).strip()]
        records = [
            {
                "evidence_id": record_id,
                "title": context.record_metadata.get(record_id, {}).get("title") or record_id,
                "source_locator": context.record_metadata.get(record_id, {}).get("source_locator") or record_id,
                "source_hash": context.record_metadata.get(record_id, {}).get("source_hash") or "",
                "text": context.record_texts.get(record_id, ""),
            }
            for record_id in record_ids
            if record_id in context.record_texts
        ]
        report = build_fact_evidence_report([claim], records)
        return {
            "status": "pass",
            "claim": claim,
            "report": report,
            "returned_source_ids": [row["evidence_id"] for row in records],
        }

    def _handle_evidence_timeline_slice(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        record_ids = [str(value).strip() for value in payload.get("record_ids") or [] if str(value).strip()]
        rows = []
        for record_id in record_ids[:20]:
            metadata = context.record_metadata.get(record_id, {})
            rows.append(
                {
                    "record_id": record_id,
                    "title": metadata.get("title") or record_id,
                    "date": metadata.get("date") or metadata.get("recorded_at") or metadata.get("created_at") or "",
                    "summary": (context.record_texts.get(record_id, "")[:160]).strip(),
                }
            )
        rows.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("record_id") or "")))
        return {"status": "pass", "timeline": rows, "returned_source_ids": [row["record_id"] for row in rows]}

    def _handle_verification_check_claims(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        claims = [str(value).strip() for value in payload.get("claims") or [] if str(value).strip()]
        source_texts = context.source_texts | context.record_texts
        source_metadata = context.source_metadata | context.record_metadata
        verifier = LegalOutputVerifier(context.authority_index)
        report = verifier.verify_output(
            text="\n".join(claims),
            source_texts=source_texts,
            source_metadata=source_metadata,
            auto_extract_claims=False,
            auto_extract_quotes=False,
        )
        return {"status": "pass", "verification_report": report, "returned_source_ids": list(source_texts.keys())[:20]}

    def _handle_review_request_human(self, payload: dict[str, Any], context: DeliberationContext) -> dict[str, Any]:
        return {
            "status": "review_requested",
            "reason": str(payload.get("reason") or "human review requested by the deliberation node"),
            "returned_source_ids": [],
        }
