from app.services.reviewer_adapter import ReviewerAdapter


def _response() -> dict:
    return {
        "answer_id": "answer-1",
        "audit_trace_id": "audit-1",
        "mode": "attorney_research",
        "audience": "attorney",
        "review_required": True,
        "red_flags": [],
        "missing_information": [{"field": "existing_orders"}],
        "filing_ready_status": "blocked_from_filing_ready",
        "claim_support_status": "unsupported_claim",
        "quote_verification_status": "citation_unverified",
        "sources_used": [],
        "citations": [],
    }


def test_reviewer_adapter_builds_queue_item_and_packet() -> None:
    adapter = ReviewerAdapter()
    queue = adapter.queue_item(_response())
    assert queue["status"] == "needs_human_review"
    assert queue["queue_id"] == "review-answer-1"

    packet = adapter.reviewer_packet(
        response=_response(),
        workflow_id="attorney_research_workflow",
        user_prompt="Please review this answer.",
    )
    assert packet["answer_id"] == "answer-1"
    assert packet["workflow_id"] == "attorney_research_workflow"
    assert packet["review_required"] is True
    assert "attorney_licensed_in_maine" in packet["reviewer_feedback_fields"]
