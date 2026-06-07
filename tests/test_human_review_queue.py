from legal.conversation.human_review_queue import HumanReviewQueueBuilder


def test_human_review_queue_item_is_deterministic_and_review_required() -> None:
    item = HumanReviewQueueBuilder().from_response(
        {
            "answer_id": "answer-1",
            "audit_trace_id": "audit-1",
            "review_required": True,
            "red_flags": [],
            "filing_ready_status": "blocked_from_filing_ready",
            "claim_support_status": "unsupported_claim",
        }
    ).as_dict()
    assert item["queue_id"] == "review-answer-1"
    assert item["status"] == "needs_human_review"
    assert "review_required" in item["reasons"]
