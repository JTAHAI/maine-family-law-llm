from legal.conversation.response_contract import ConversationResponseBuilder, REQUIRED_RESPONSE_FIELDS


def test_response_contract_builder_populates_required_fields() -> None:
    builder = ConversationResponseBuilder()
    response = builder.build(
        mode="attorney_research",
        audience="attorney",
        jurisdiction_scope="maine_only",
        issue_labels=["child_support"],
        procedural_posture="initial_complaint",
        task_type="query",
        source_scope_status="source_unknown_freshness",
        source_freshness_status="source_unknown_freshness",
        short_answer="Review required.",
        explanation="Review required.",
        plain_language_explanation="Review required.",
        attorney_notes="Check the source cards.",
        sources_used=[],
        source_cards=[],
        citations=[],
        quote_verification_status="citation_unverified",
        claim_support_status="unsupported_claim",
        missing_information=[],
        warnings=[],
        red_flags=[],
        filing_ready_status="blocked_from_filing_ready",
        filing_ready_blockers=["review_required"],
    ).as_dict()

    assert set(REQUIRED_RESPONSE_FIELDS).issubset(response)
    assert response["review_required"] is True
    assert response["filing_ready_status"] == "blocked_from_filing_ready"
