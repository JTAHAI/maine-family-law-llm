from legal.conversation.reviewer_packet import ReviewerPacketBuilder


def test_reviewer_packet_redacts_prompt_and_contains_feedback_fields() -> None:
    packet = ReviewerPacketBuilder().build(
        response={
            "answer_id": "answer-1",
            "audit_trace_id": "audit-1",
            "mode": "attorney_research",
            "audience": "attorney",
            "sources_used": [],
            "citations": [],
            "quote_verification_status": "citation_unverified",
            "claim_support_status": "unsupported_claim",
            "red_flags": [],
            "missing_information": [],
            "filing_ready_status": "blocked_from_filing_ready",
            "review_required": True,
            "short_answer": "Review required.",
        },
        workflow_id="attorney_research_workflow",
        user_prompt="DOB 1/2/2010 review custody.",
    )
    assert "[redacted-date]" in packet["user_prompt_redacted"]
    assert "reviewer_role" in packet["reviewer_feedback_fields"]
    assert packet["review_required"] is True
