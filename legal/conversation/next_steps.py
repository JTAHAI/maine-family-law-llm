from __future__ import annotations

from typing import Any


class ConversationNextStepsBuilder:
    def build(self, response: dict[str, Any]) -> list[str]:
        steps: list[str] = []
        missing = response.get("missing_information") or []
        if missing:
            first = missing[0]
            if isinstance(first, dict):
                steps.append(str(first.get("audience_prompt") or f"Provide {first.get('field', 'missing information')}."))
        if response.get("source_scope_status") != "source_verified":
            steps.append("Verify source freshness and Maine jurisdiction before relying on legal conclusions.")
        if response.get("citations") and response.get("claim_support_status") != "source_verified":
            steps.append("Run citation and claim-support checks.")
        if response.get("quote_verification_status") == "quote_span_not_found":
            steps.append("Match quoted language to a source span or remove it.")
        if response.get("filing_ready_status") != "filing_ready_passed":
            steps.append("Keep this blocked from filing-ready use.")
        steps.append("Send to human review before relying on the output.")
        return list(dict.fromkeys(steps))
