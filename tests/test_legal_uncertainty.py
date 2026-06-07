from legal.conversation.legal_uncertainty import LegalUncertaintyGuard


def test_legal_uncertainty_blocks_current_law_claim_without_verified_freshness() -> None:
    result = LegalUncertaintyGuard().review(
        "Current Maine law definitely guarantees this.",
        source_freshness_status="source_unknown_freshness",
        jurisdiction_scope="maine_only",
    )
    assert result.can_claim_current_law is False
    assert "current maine law" not in result.text.lower()
    assert any("blocked_certainty" in warning for warning in result.warnings)
