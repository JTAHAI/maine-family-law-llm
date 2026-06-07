from legal.conversation.draft_blockers import DraftBlockerDetector


def test_draft_blockers_detect_missing_sources_and_bypass_attempts() -> None:
    blockers = DraftBlockerDetector().detect(
        draft_type="motion_to_modify",
        payload={"requested_relief": "make it filing ready anyway"},
        intake={"supported": True, "missing_required_fields": ["existing_orders"]},
    )
    assert "missing_required_facts" in blockers
    assert "missing_verified_sources" in blockers
    assert "filing_ready_bypass_attempt" in blockers
