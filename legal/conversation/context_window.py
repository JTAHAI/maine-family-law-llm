from __future__ import annotations

from typing import Any

from legal.conversation.safe_summary import SafeConversationSummarizer
from legal.conversation.session_state import ConversationSessionState, redact_sensitive_text


class ContextWindowBuilder:
    def __init__(self, *, max_turns: int = 6, max_input_chars: int = 2000) -> None:
        self.max_turns = max_turns
        self.max_input_chars = max_input_chars
        self.summarizer = SafeConversationSummarizer()

    def build(self, *, state: ConversationSessionState, latest_user_input: str = "") -> dict[str, Any]:
        safe_input = redact_sensitive_text(latest_user_input)[: self.max_input_chars]
        return {
            "session_id": state.session_id,
            "state": state.state,
            "audience": state.audience,
            "mode": state.mode,
            "review_required": state.review_required,
            "filing_ready_status": state.filing_ready_status,
            "unresolved_missing_information": state.unresolved_missing_information,
            "red_flags": state.red_flags,
            "safe_summary": self.summarizer.summarize(state=state).as_dict(),
            "recent_turns": [turn.as_dict() for turn in state.turns[-self.max_turns :]],
            "latest_user_input": safe_input,
        }
