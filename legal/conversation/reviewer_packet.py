from __future__ import annotations

from typing import Any

from legal.conversation.session_state import redact_sensitive_text


class ReviewerPacketBuilder:
    def build(
        self,
        *,
        response: dict[str, Any],
        workflow_id: str,
        user_prompt: str,
        output_text: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema": "maine_family_law_llm.reviewer_packet_v1",
            "answer_id": response.get("answer_id"),
            "audit_trace_id": response.get("audit_trace_id"),
            "mode": response.get("mode"),
            "audience": response.get("audience"),
            "workflow_id": workflow_id,
            "user_prompt_redacted": redact_sensitive_text(user_prompt),
            "output_text": output_text or response.get("short_answer") or "",
            "response_contract_json": response,
            "sources_used": response.get("sources_used", []),
            "citation_statuses": response.get("citations", []),
            "quote_statuses": [response.get("quote_verification_status")],
            "claim_support_statuses": [response.get("claim_support_status")],
            "red_flags": response.get("red_flags", []),
            "missing_information": response.get("missing_information", []),
            "filing_ready_status": response.get("filing_ready_status"),
            "review_required": response.get("review_required", True),
            "reviewer_questions": [
                "Are the cited sources real, current, and correctly characterized?",
                "Is any plain-language explanation accurate and not overconfident?",
                "Are any safety, jurisdiction, confidentiality, or filing-ready blockers missing?",
            ],
            "reviewer_feedback_fields": [
                "reviewer_role",
                "attorney_licensed_in_maine",
                "reviewed_sources",
                "reviewed_citations",
                "legal_accuracy_rating",
                "blocking_issue",
                "comments",
                "evidence_file_path",
            ],
        }
