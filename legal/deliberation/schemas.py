from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA_VERSION = "deliberation_node_v1"
SOURCE_LANES = (
    "legal_authority",
    "private_record",
    "model_analysis",
    "prefrontal_ledger",
    "deterministic_verifier_output",
)
RUN_STATUSES = {
    "draft_scope",
    "awaiting_local_confirmation",
    "queued",
    "running_independent",
    "aligning_claims",
    "cross_review",
    "rebuttal",
    "omission_hunt",
    "final_positions",
    "verifying",
    "synthesizing",
    "completed_review_required",
    "partial_worker_failure",
    "budget_exhausted",
    "cancelling",
    "cancelled",
    "failed_closed",
}
CONSENT_MODES = {"local_only"}
CLAIM_STATUSES = {
    "source_supported",
    "evidence_supported",
    "partially_supported",
    "contradicted",
    "unverified",
    "unknown",
    "stale_or_jurisdiction_risk",
    "worker_disagreement",
    "review_required",
}
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(payload: Any) -> str:
    return sha256(canonical_json(payload)).hexdigest()


def safe_identifier(value: str, *, fallback: str) -> str:
    cleaned = _SAFE_ID_RE.sub("-", str(value or "").strip()).strip("-.")
    return (cleaned or fallback)[:160]


@dataclass(frozen=True)
class DeliberationLimit:
    max_rounds: int = 5
    time_limit_seconds: int = 600
    token_limit: int = 120_000
    context_limit_chars: int = 80_000
    tool_call_limit: int = 12
    worker_call_limit: int = 12
    max_output_chars: int = 20_000

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_rounds": self.max_rounds,
            "time_limit_seconds": self.time_limit_seconds,
            "token_limit": self.token_limit,
            "context_limit_chars": self.context_limit_chars,
            "tool_call_limit": self.tool_call_limit,
            "worker_call_limit": self.worker_call_limit,
            "max_output_chars": self.max_output_chars,
        }


@dataclass(frozen=True)
class ScopeFreeze:
    exact_question: str
    included_records: list[dict[str, Any]]
    excluded_records: list[dict[str, Any]]
    included_authority_sources: list[dict[str, Any]]
    date_range: dict[str, str]
    issue_filters: list[str]
    posture_filters: list[str]
    output_type: str
    worker_set: list[str]
    allowed_tools: list[str]
    context_budget: dict[str, int]
    consent_mode: str = "local_only"
    configuration_hash: str = ""
    frozen_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "exact_question": self.exact_question,
            "included_records": [dict(row) for row in self.included_records],
            "excluded_records": [dict(row) for row in self.excluded_records],
            "included_authority_sources": [dict(row) for row in self.included_authority_sources],
            "date_range": dict(self.date_range),
            "issue_filters": list(self.issue_filters),
            "posture_filters": list(self.posture_filters),
            "output_type": self.output_type,
            "worker_set": list(self.worker_set),
            "allowed_tools": list(self.allowed_tools),
            "context_budget": dict(self.context_budget),
            "consent_mode": self.consent_mode,
            "configuration_hash": self.configuration_hash,
            "frozen_at": self.frozen_at,
        }


@dataclass(frozen=True)
class WorkerTurnRequest:
    run_id: str
    round: int
    role: str
    task: str
    approved_context_packet: dict[str, Any]
    prior_anonymized_structured_positions: list[dict[str, Any]]
    output_schema: dict[str, Any]
    limits: dict[str, Any]
    tool_grants: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "round": self.round,
            "role": self.role,
            "task": self.task,
            "approved_context_packet": dict(self.approved_context_packet),
            "prior_anonymized_structured_positions": [dict(row) for row in self.prior_anonymized_structured_positions],
            "output_schema": dict(self.output_schema),
            "limits": dict(self.limits),
            "tool_grants": [dict(row) for row in self.tool_grants],
        }


@dataclass(frozen=True)
class WorkerTurnResult:
    worker_id: str
    model_runtime_metadata: dict[str, Any]
    round: int
    claims: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    concise_rationale_summaries: list[str]
    critiques: list[dict[str, Any]]
    omissions: list[dict[str, Any]]
    assumptions: list[str]
    requested_sources: list[dict[str, Any]]
    confidence_category: str
    usage: dict[str, Any]
    finish_status: str
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "model_runtime_metadata": dict(self.model_runtime_metadata),
            "round": self.round,
            "claims": [dict(row) for row in self.claims],
            "source_refs": [dict(row) for row in self.source_refs],
            "concise_rationale_summaries": list(self.concise_rationale_summaries),
            "critiques": [dict(row) for row in self.critiques],
            "omissions": [dict(row) for row in self.omissions],
            "assumptions": list(self.assumptions),
            "requested_sources": [dict(row) for row in self.requested_sources],
            "confidence_category": self.confidence_category,
            "usage": dict(self.usage),
            "finish_status": self.finish_status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ClaimLedgerEntry:
    canonical_claim: str
    claim_type: str
    materiality: str
    worker_positions: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    record_refs: list[dict[str, Any]]
    supporting_spans: list[dict[str, Any]]
    contradicting_spans: list[dict[str, Any]]
    verifier_status: str
    history: list[dict[str, Any]]
    unresolved_questions: list[str]
    narrower_claims: list[str] = field(default_factory=list)
    broader_claims: list[str] = field(default_factory=list)
    conflicting_qualifications: list[str] = field(default_factory=list)
    withdrawn_claims: list[str] = field(default_factory=list)
    corrected_claims: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_claim": self.canonical_claim,
            "claim_type": self.claim_type,
            "materiality": self.materiality,
            "worker_positions": [dict(row) for row in self.worker_positions],
            "source_refs": [dict(row) for row in self.source_refs],
            "record_refs": [dict(row) for row in self.record_refs],
            "supporting_spans": [dict(row) for row in self.supporting_spans],
            "contradicting_spans": [dict(row) for row in self.contradicting_spans],
            "verifier_status": self.verifier_status,
            "history": [dict(row) for row in self.history],
            "unresolved_questions": list(self.unresolved_questions),
            "narrower_claims": list(self.narrower_claims),
            "broader_claims": list(self.broader_claims),
            "conflicting_qualifications": list(self.conflicting_qualifications),
            "withdrawn_claims": list(self.withdrawn_claims),
            "corrected_claims": list(self.corrected_claims),
        }


@dataclass(frozen=True)
class ToolCallRecord:
    run_id: str
    worker: str
    tool: str
    validated_argument_hash: str
    policy_result: str
    returned_source_ids: list[str]
    duration_ms: int
    status: str
    created_at: str
    token_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "worker": self.worker,
            "tool": self.tool,
            "validated_argument_hash": self.validated_argument_hash,
            "policy_result": self.policy_result,
            "returned_source_ids": list(self.returned_source_ids),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "created_at": self.created_at,
            "token_id": self.token_id,
        }


@dataclass(frozen=True)
class FinalSynthesis:
    scope: dict[str, Any]
    what_sources_establish: list[dict[str, Any]]
    agreement: list[str]
    dissent: list[dict[str, Any]]
    verified_legal_support: list[dict[str, Any]]
    verified_record_support: list[dict[str, Any]]
    unsupported_claims: list[dict[str, Any]]
    contradicted_claims: list[dict[str, Any]]
    stale_jurisdiction_risks: list[dict[str, Any]]
    missing_information: list[dict[str, Any]]
    provider_worker_failures: list[dict[str, Any]]
    next_review_steps: list[str]
    review_status: str
    unresolved_questions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": dict(self.scope),
            "what_sources_establish": [dict(row) for row in self.what_sources_establish],
            "agreement": list(self.agreement),
            "dissent": [dict(row) for row in self.dissent],
            "verified_legal_support": [dict(row) for row in self.verified_legal_support],
            "verified_record_support": [dict(row) for row in self.verified_record_support],
            "unsupported_claims": [dict(row) for row in self.unsupported_claims],
            "contradicted_claims": [dict(row) for row in self.contradicted_claims],
            "stale_jurisdiction_risks": [dict(row) for row in self.stale_jurisdiction_risks],
            "missing_information": [dict(row) for row in self.missing_information],
            "provider_worker_failures": [dict(row) for row in self.provider_worker_failures],
            "next_review_steps": list(self.next_review_steps),
            "review_status": self.review_status,
            "unresolved_questions": list(self.unresolved_questions),
        }


@dataclass(frozen=True)
class DeliberationEvent:
    event_id: str
    run_id: str
    event_type: str
    round: int
    state: str
    summary: str
    details: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "round": self.round,
            "state": self.state,
            "summary": self.summary,
            "details": dict(self.details),
            "created_at": self.created_at,
        }


@dataclass
class DeliberationRun:
    run_id: str
    matter_id: str
    question: str
    user_role: str
    jurisdiction: str
    date_range: dict[str, str]
    desired_output: str
    source_lanes: list[str]
    worker_set: list[str]
    worker_roles: list[str]
    limits: DeliberationLimit
    status: str = "draft_scope"
    review_status: str = "review_required"
    cancellation_state: str = "active"
    scope_freeze: ScopeFreeze | None = None
    events: list[DeliberationEvent] = field(default_factory=list)
    claims: list[ClaimLedgerEntry] = field(default_factory=list)
    positions: list[dict[str, Any]] = field(default_factory=list)
    synthesis: FinalSynthesis | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    confirmed_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    cancelled_at: str = ""
    last_error: str = ""
    configuration_hash: str = ""
    tool_call_count: int = 0
    worker_turn_count: int = 0
    verifier_status: str = "review_required"
    restart_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "matter_id": self.matter_id,
            "question": self.question,
            "user_role": self.user_role,
            "jurisdiction": self.jurisdiction,
            "date_range": dict(self.date_range),
            "desired_output": self.desired_output,
            "source_lanes": list(self.source_lanes),
            "worker_set": list(self.worker_set),
            "worker_roles": list(self.worker_roles),
            "limits": self.limits.as_dict(),
            "status": self.status,
            "review_status": self.review_status,
            "cancellation_state": self.cancellation_state,
            "scope_freeze": self.scope_freeze.as_dict() if self.scope_freeze else None,
            "events": [event.as_dict() for event in self.events],
            "claims": [claim.as_dict() for claim in self.claims],
            "positions": [dict(row) for row in self.positions],
            "synthesis": self.synthesis.as_dict() if self.synthesis else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confirmed_at": self.confirmed_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "last_error": self.last_error,
            "configuration_hash": self.configuration_hash,
            "tool_call_count": self.tool_call_count,
            "worker_turn_count": self.worker_turn_count,
            "verifier_status": self.verifier_status,
            "restart_count": self.restart_count,
        }
