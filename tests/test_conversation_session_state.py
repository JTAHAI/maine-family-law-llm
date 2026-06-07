from legal.conversation.session_state import ConversationSessionState


def test_session_state_redacts_sensitive_turns_and_labels_facts() -> None:
    state = ConversationSessionState(session_id="s1")
    state.add_turn("user", "My SSN is 123-45-6789 and DOB is 1/2/2010.")
    state.add_fact("Existing order mentioned by user", label="user_stated")
    payload = state.as_dict()

    assert "123-45-6789" not in payload["turns"][0]["content"]
    assert payload["facts"][0]["label"] == "user_stated"


def test_session_state_preserves_unresolved_missing_information() -> None:
    state = ConversationSessionState(session_id="s1")
    state.merge_response(
        {
            "audience": "attorney",
            "mode": "attorney_research",
            "missing_information": [{"field": "existing_orders"}],
            "red_flags": ["deadline risk"],
            "review_required": True,
            "filing_ready_status": "blocked_from_filing_ready",
        }
    )
    assert state.audience == "attorney"
    assert state.unresolved_missing_information[0]["field"] == "existing_orders"
    assert "deadline risk" in state.red_flags
