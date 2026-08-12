"""Host-controlled, read-only tool broker for local model workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Callable

from .contracts import canonical_json, safe_identifier, utc_now

MAX_TOOL_CALLS = 12
MAX_ARGS_BYTES = 32 * 1024
MAX_RESULT_BYTES = 256 * 1024


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    lane: str
    capability: str
    description: str
    requires_matter_scope: bool = False
    max_calls_per_run: int = 4


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolReceipt:
    call_id: str
    tool_name: str
    lane: str
    capability: str
    status: str
    args_sha256: str
    result_sha256: str
    result_preview: str
    created_at: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "local_agent_tool_receipt_v1",
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "lane": self.lane,
            "capability": self.capability,
            "status": self.status,
            "args_sha256": self.args_sha256,
            "result_sha256": self.result_sha256,
            "result_preview": self.result_preview,
            "created_at": self.created_at,
            "receipt_sha256": self.receipt_sha256,
        }


_DEFAULT_DEFINITIONS = (
    ToolDefinition("authority.search", "legal_authority", "read_search", "Search approved Maine authority."),
    ToolDefinition("authority.get_span", "legal_authority", "read_span", "Return one bounded authority span."),
    ToolDefinition("authority.verify_citation", "verifier", "verify", "Resolve one citation."),
    ToolDefinition("records.search", "private_record", "read_search", "Search the active matter.", requires_matter_scope=True),
    ToolDefinition("records.get_slice", "private_record", "read_span", "Return one bounded record slice.", requires_matter_scope=True),
    ToolDefinition("evidence.map_claim", "evidence", "analyze", "Map a claim to selected records.", requires_matter_scope=True),
    ToolDefinition("verification.check_claims", "verifier", "verify", "Run deterministic support checks."),
)


class CapabilityToolBroker:
    """Executes only handlers registered by the host application.

    The model never receives a filesystem, shell, package, network, credential,
    deletion, or record-modification capability through this broker.
    """

    def __init__(self, definitions: tuple[ToolDefinition, ...] = _DEFAULT_DEFINITIONS):
        self.definitions = {definition.name: definition for definition in definitions}
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, tool_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if tool_name not in self.definitions:
            raise KeyError(f"tool_not_allowlisted:{tool_name}")
        self.handlers[tool_name] = handler

    def execute_many(
        self,
        invocations: list[ToolInvocation],
        *,
        run_id: str,
        permitted_tools: set[str],
        matter_id: str | None = None,
        max_calls: int = MAX_TOOL_CALLS,
    ) -> tuple[list[Any], list[ToolReceipt]]:
        if len(invocations) > min(max_calls, MAX_TOOL_CALLS):
            raise ValueError("local_agent_tool_call_limit_exceeded")
        per_tool: dict[str, int] = {}
        results: list[Any] = []
        receipts: list[ToolReceipt] = []
        for offset, invocation in enumerate(invocations, start=1):
            definition = self.definitions.get(invocation.name)
            if definition is None or invocation.name not in permitted_tools:
                raise PermissionError(f"local_agent_tool_not_permitted:{invocation.name}")
            if definition.requires_matter_scope and not matter_id:
                raise PermissionError(f"local_agent_matter_scope_required:{invocation.name}")
            per_tool[invocation.name] = per_tool.get(invocation.name, 0) + 1
            if per_tool[invocation.name] > definition.max_calls_per_run:
                raise ValueError(f"local_agent_per_tool_limit_exceeded:{invocation.name}")
            handler = self.handlers.get(invocation.name)
            if handler is None:
                raise RuntimeError(f"local_agent_tool_handler_missing:{invocation.name}")
            args_bytes = canonical_json(invocation.args)
            if len(args_bytes) > MAX_ARGS_BYTES:
                raise ValueError(f"local_agent_tool_args_too_large:{invocation.name}")
            result = handler(dict(invocation.args))
            result_bytes = canonical_json(result)
            if len(result_bytes) > MAX_RESULT_BYTES:
                raise ValueError(f"local_agent_tool_result_too_large:{invocation.name}")
            results.append(result)
            preview = result_bytes.decode("utf-8", errors="replace")
            if len(preview) > 500:
                preview = preview[:497] + "..."
            created_at = utc_now()
            base = {
                "call_id": safe_identifier(f"{run_id}-{offset}", fallback=f"call-{offset}"),
                "tool_name": invocation.name,
                "lane": definition.lane,
                "capability": definition.capability,
                "status": "completed",
                "args_sha256": sha256(args_bytes).hexdigest(),
                "result_sha256": sha256(result_bytes).hexdigest(),
                "result_preview": preview,
                "created_at": created_at,
            }
            receipt_sha256 = sha256(canonical_json(base)).hexdigest()
            receipts.append(ToolReceipt(receipt_sha256=receipt_sha256, **base))
        return results, receipts

    def public_catalog(self) -> list[dict[str, Any]]:
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
