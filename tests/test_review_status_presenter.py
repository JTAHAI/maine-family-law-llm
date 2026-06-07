from legal.conversation.review_status_presenter import ReviewStatusPresenter


def test_review_status_presenter_keeps_review_and_filing_status_visible() -> None:
    status = ReviewStatusPresenter().present(
        {"review_required": True, "filing_ready_status": "blocked_from_filing_ready", "filing_ready_blockers": ["review_required"]}
    )
    assert status["review_label"] == "Review required"
    assert status["filing_ready_label"] == "Blocked from filing-ready use"
