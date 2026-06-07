from legal.conversation.next_steps import ConversationNextStepsBuilder


def test_next_steps_surface_missing_source_and_filing_blockers() -> None:
    steps = ConversationNextStepsBuilder().build(
        {
            "missing_information": [{"field": "requested_relief", "audience_prompt": "What are you asking for?"}],
            "source_scope_status": "source_unknown_freshness",
            "quote_verification_status": "quote_span_not_found",
            "filing_ready_status": "blocked_from_filing_ready",
        }
    )
    assert "What are you asking for?" in steps
    assert any("source freshness" in step for step in steps)
    assert any("filing-ready" in step for step in steps)
