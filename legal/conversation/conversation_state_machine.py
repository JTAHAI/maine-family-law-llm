from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legal.conversation.session_state import ConversationSessionState


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_conversation_state_machine.json"


class ConversationStateMachine:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.states = set(str(item) for item in self.config.get("states", []))

    def transition(
        self,
        state: ConversationSessionState,
        *,
        user_input: str = "",
        task_type: str = "query",
        response: dict[str, Any] | None = None,
    ) -> ConversationSessionState:
        response = response or {}
        text = user_input.lower()
        missing = response.get("missing_information") or state.unresolved_missing_information
        red_flags = [str(item) for item in response.get("red_flags") or state.red_flags]
        jurisdiction = str(response.get("jurisdiction_scope") or "")
        quote_status = str(response.get("quote_verification_status") or "")
        claim_status = str(response.get("claim_support_status") or "")
        source_status = str(response.get("source_scope_status") or "")

        if any(flag for flag in red_flags if "emergency" in flag.lower() or "safety" in flag.lower()):
            next_state = "emergency_or_safety_escalation"
        elif jurisdiction in {"not_maine", "federal_overlap"}:
            next_state = "out_of_scope"
        elif "filing ready" in text or task_type == "filing_ready_check":
            next_state = "filing_ready_blocked"
        elif task_type == "draft":
            next_state = "draft_blocked_missing_facts" if missing else "draft_ready_review_required"
        elif task_type == "citation_verification" or response.get("citations"):
            next_state = "citation_verification_needed"
        elif task_type == "quote_verification" or quote_status == "quote_span_not_found":
            next_state = "quote_verification_needed"
        elif task_type == "evidence_map":
            next_state = "evidence_mapping_needed"
        elif missing:
            next_state = "missing_information_followup"
        elif source_status != "source_verified" or claim_status in {"unsupported_claim", "partially_supported_claim"}:
            next_state = "source_review_needed"
        else:
            next_state = "answer_ready_review_required"

        if next_state not in self.states:
            next_state = "new_session"
        state.state = next_state
        state.merge_response(response)
        return state
