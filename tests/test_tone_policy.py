from legal.conversation import TonePolicy


def test_tone_policy_rewrites_unsafe_certainty_and_filing_ready_claims() -> None:
    policy = TonePolicy()
    result = policy.apply(
        "This is filing ready and the outcome is a guaranteed outcome.",
        source_freshness_status="source_unknown_freshness",
        jurisdiction_scope="jurisdiction_unknown",
    )

    assert "blocked from filing-ready" in result.text
    assert "guaranteed outcome" not in result.text
    assert any("tone_rewrite" in warning for warning in result.warnings)


def test_tone_policy_emits_escalation_for_emergency_language() -> None:
    policy = TonePolicy()
    result = policy.apply("There is an emergency and the client is unsafe tonight.")
    assert result.escalation_messages
