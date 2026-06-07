from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


REQUIRED_RESPONSE_FIELDS = (
    "answer_id",
    "audit_trace_id",
    "created_at",
    "mode",
    "audience",
    "jurisdiction_scope",
    "issue_labels",
    "procedural_posture",
    "task_type",
    "source_scope_status",
    "source_freshness_status",
    "short_answer",
    "explanation",
    "plain_language_explanation",
    "attorney_notes",
    "sources_used",
    "source_cards",
    "citations",
    "quote_verification_status",
    "claim_support_status",
    "missing_information",
    "warnings",
    "red_flags",
    "filing_ready_status",
    "filing_ready_blockers",
    "review_required",
    "next_steps",
    "confidence",
    "limitations",
)


@dataclass
class ConversationResponse:
    answer_id: str
    audit_trace_id: str
    created_at: str
    mode: str
    audience: str
    jurisdiction_scope: str
    issue_labels: list[str]
    procedural_posture: str
    task_type: str
    source_scope_status: str
    source_freshness_status: str
    short_answer: str
    explanation: str
    plain_language_explanation: str
    attorney_notes: str
    sources_used: list[dict[str, Any]]
    source_cards: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    quote_verification_status: str
    claim_support_status: str
    missing_information: list[dict[str, Any]]
    warnings: list[str]
    red_flags: list[str]
    filing_ready_status: str
    filing_ready_blockers: list[str]
    review_required: bool = True
    next_steps: list[str] = field(default_factory=list)
    confidence: float = 0.0
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {field_name: getattr(self, field_name) for field_name in REQUIRED_RESPONSE_FIELDS}


class ConversationResponseBuilder:
    def build(
        self,
        *,
        mode: str,
        audience: str,
        jurisdiction_scope: str,
        issue_labels: list[str],
        procedural_posture: str,
        task_type: str,
        source_scope_status: str,
        source_freshness_status: str,
        short_answer: str,
        explanation: str,
        plain_language_explanation: str,
        attorney_notes: str,
        sources_used: list[dict[str, Any]],
        source_cards: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        quote_verification_status: str,
        claim_support_status: str,
        missing_information: list[dict[str, Any]],
        warnings: list[str],
        red_flags: list[str],
        filing_ready_status: str,
        filing_ready_blockers: list[str],
        review_required: bool = True,
        next_steps: list[str] | None = None,
        confidence: float = 0.0,
        limitations: list[str] | None = None,
    ) -> ConversationResponse:
        seed = {
            "mode": mode,
            "audience": audience,
            "task_type": task_type,
            "short_answer": short_answer,
            "source_scope_status": source_scope_status,
        }
        digest = hashlib.sha256(json.dumps(seed, sort_keys=True).encode("utf-8")).hexdigest()
        return ConversationResponse(
            answer_id=f"answer-{digest[:12]}",
            audit_trace_id=f"audit-{digest[12:24]}",
            created_at=datetime.now(UTC).isoformat(),
            mode=mode,
            audience=audience,
            jurisdiction_scope=jurisdiction_scope,
            issue_labels=issue_labels,
            procedural_posture=procedural_posture,
            task_type=task_type,
            source_scope_status=source_scope_status,
            source_freshness_status=source_freshness_status,
            short_answer=short_answer,
            explanation=explanation,
            plain_language_explanation=plain_language_explanation,
            attorney_notes=attorney_notes,
            sources_used=sources_used,
            source_cards=source_cards,
            citations=citations,
            quote_verification_status=quote_verification_status,
            claim_support_status=claim_support_status,
            missing_information=missing_information,
            warnings=warnings,
            red_flags=red_flags,
            filing_ready_status=filing_ready_status,
            filing_ready_blockers=filing_ready_blockers,
            review_required=review_required,
            next_steps=next_steps or [],
            confidence=round(float(confidence), 3),
            limitations=limitations or [],
        )
