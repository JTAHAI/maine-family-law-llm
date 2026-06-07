from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class HumanReviewQueueItem:
    queue_id: str
    answer_id: str
    audit_trace_id: str
    priority: str
    reasons: list[str]
    status: str = "needs_human_review"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "answer_id": self.answer_id,
            "audit_trace_id": self.audit_trace_id,
            "priority": self.priority,
            "reasons": self.reasons,
            "status": self.status,
            "created_at": self.created_at,
        }


class HumanReviewQueueBuilder:
    def from_response(self, response: dict[str, Any]) -> HumanReviewQueueItem:
        reasons = []
        if response.get("review_required", True):
            reasons.append("review_required")
        if response.get("red_flags"):
            reasons.append("red_flags_present")
        if response.get("filing_ready_status") != "filing_ready_passed":
            reasons.append("filing_ready_blocked")
        if response.get("claim_support_status") != "source_verified":
            reasons.append("source_or_claim_support_unverified")
        priority = "high" if response.get("red_flags") else "normal"
        return HumanReviewQueueItem(
            queue_id=f"review-{response.get('answer_id', 'unknown')}",
            answer_id=str(response.get("answer_id") or "unknown"),
            audit_trace_id=str(response.get("audit_trace_id") or "unknown"),
            priority=priority,
            reasons=list(dict.fromkeys(reasons)),
        )
