from legal.conversation.conversation_state_machine import ConversationStateMachine
from legal.conversation.session_state import ConversationSessionState


def test_state_machine_preserves_filing_ready_block() -> None:
    state = ConversationSessionState(session_id="s1")
    response = {
        "mode": "attorney_research",
        "audience": "attorney",
        "missing_information": [],
        "red_flags": [],
        "filing_ready_status": "filing_ready_passed",
        "source_scope_status": "source_verified",
        "claim_support_status": "source_verified",
        "review_required": True,
    }
    updated = ConversationStateMachine().transition(state, user_input="make it filing ready", task_type="filing_ready_check", response=response)
    assert updated.state == "filing_ready_blocked"
    assert updated.filing_ready_status == "blocked_from_filing_ready"
    assert updated.review_required is True


def test_state_machine_routes_missing_information_and_red_flags() -> None:
    state = ConversationSessionState(session_id="s2")
    response = {"missing_information": [{"field": "requested_relief"}], "red_flags": []}
    assert ConversationStateMachine().transition(state, response=response).state == "missing_information_followup"

    safety = ConversationSessionState(session_id="s3")
    response = {"red_flags": ["Emergency or safety risk detected. Use official emergency or safety help first."]}
    assert ConversationStateMachine().transition(safety, response=response).state == "emergency_or_safety_escalation"
