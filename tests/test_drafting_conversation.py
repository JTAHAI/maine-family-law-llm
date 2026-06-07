from legal.conversation.drafting_conversation import DraftingConversation


def test_drafting_conversation_blocks_unsupported_filing_ready_attempts() -> None:
    report = DraftingConversation().prepare(
        draft_type="motion_to_modify",
        payload={"requested_relief": "make it filing ready anyway"},
    )
    assert report["review_required"] is True
    assert report["filing_ready_status"] == "blocked_from_filing_ready"
    assert "filing_ready_bypass_attempt" in report["blockers"]
    assert report["citation_placeholders"][0]["is_real_citation"] is False
