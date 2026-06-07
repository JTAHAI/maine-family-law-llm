from legal.conversation import ConversationModeCatalog


def test_conversation_mode_catalog_contains_required_modes() -> None:
    catalog = ConversationModeCatalog()
    assert {
        "attorney_research",
        "attorney_drafting",
        "paralegal_review",
        "self_represented_plain_language",
        "form_guidance",
        "document_review",
        "appellate_issue_spotting",
        "evidence_mapping",
        "citation_verification",
        "quote_verification",
        "filing_readiness_review",
        "admin_audit",
    }.issubset(catalog.required_modes())


def test_conversation_mode_routing_prefers_audience_and_issue_overrides() -> None:
    catalog = ConversationModeCatalog()
    assert catalog.route(audience="attorney", task_type="query").mode == "attorney_research"
    assert catalog.route(audience="paralegal", task_type="evidence_map").mode == "evidence_mapping"
    assert catalog.route(audience="attorney", task_type="quote_verification").mode == "quote_verification"
    assert (
        catalog.route(
            audience="attorney",
            task_type="review",
            issue_labels=["appeal"],
        ).mode
        == "appellate_issue_spotting"
    )
    assert catalog.route(audience="unknown", task_type="query").mode == "self_represented_plain_language"
