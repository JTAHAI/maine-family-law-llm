from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal.conversation.session_state import ConversationSessionState, SessionFact, safe_payload_facts


@dataclass(frozen=True)
class SafeSummary:
    summary: str
    facts: list[dict[str, str]]
    omitted_sensitive_detail: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "facts": self.facts,
            "omitted_sensitive_detail": self.omitted_sensitive_detail,
        }


class SafeConversationSummarizer:
    def summarize(
        self,
        *,
        state: ConversationSessionState | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SafeSummary:
        facts: list[SessionFact] = []
        if state is not None:
            facts.extend(state.facts)
        if payload:
            facts.extend(safe_payload_facts(payload))
        fact_rows = [fact.as_dict() for fact in facts]
        omitted_sensitive = any("[sensitive detail omitted]" in row["text"] for row in fact_rows)
        summary_bits = [row["text"] for row in fact_rows[:8]]
        summary = "; ".join(summary_bits) if summary_bits else "No durable facts have been verified yet."
        return SafeSummary(
            summary=summary,
            facts=fact_rows,
            omitted_sensitive_detail=omitted_sensitive,
        )
