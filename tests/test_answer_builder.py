from legal.conversation.answer_builder import ConversationalAnswerBuilder


def _response() -> dict:
    return {
        "mode": "self_represented_plain_language",
        "audience": "self_represented",
        "short_answer": "This is definitely current Maine law and you will win.",
        "explanation": "Review required.",
        "plain_language_explanation": "What this means: review is required.",
        "source_scope_status": "source_unknown_freshness",
        "source_freshness_status": "source_unknown_freshness",
        "jurisdiction_scope": "maine_only",
        "claim_support_status": "unsupported_claim",
        "source_cards": [],
        "citations": [],
        "missing_information": [{"field": "requested_relief", "audience_prompt": "What are you asking for?"}],
        "red_flags": [],
        "review_required": True,
        "filing_ready_status": "blocked_from_filing_ready",
        "filing_ready_blockers": ["review_required"],
    }


def test_answer_builder_outputs_stable_sections_and_blocks_certainty() -> None:
    answer = ConversationalAnswerBuilder().build(_response())
    section_names = [row["section"] for row in answer["ordered_sections"]]
    assert section_names[0] == "direct_answer_or_status"
    assert "you will win" not in answer["text"].lower()
    assert "current maine law" not in answer["text"].lower()
    assert answer["review_required"] is True
    assert answer["filing_ready_status"] == "blocked_from_filing_ready"
