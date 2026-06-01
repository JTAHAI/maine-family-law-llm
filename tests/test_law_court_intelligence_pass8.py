from legal.law_court import LawCourtIntelligenceExtractor


def test_law_court_intelligence_extracts_appellate_signals():
    extractor = LawCourtIntelligenceExtractor()
    text = (
        "The mother appeals from a post-judgment order concerning parental rights and "
        "responsibilities. We review for abuse of discretion and clear error. "
        "We vacate and remand because the court failed to make findings required by "
        "Rule 52 and did not address the best interest factors. The record includes "
        "no transcript, and the order delegated contact decisions to a therapist."
    )

    brief = extractor.extract_case_brief(text, source_id="source-2025-me-1", citation="2025 ME 1")

    assert brief["procedural_posture"] == "post_judgment_appeal"
    assert brief["standard_of_review"] == "mixed"
    assert brief["disposition"] == "remanded"
    assert "Rule_52_findings" in brief["issue_labels"]
    assert "best_interest_factor_gap" in brief["issue_labels"]
    assert "transcript_record_issue" in brief["issue_labels"]
    assert "therapist_non_delegation" in brief["issue_labels"]
    assert "missing Rule 52 findings" in brief["red_flags"]
    assert "therapist or third-party delegated contact decision" in brief["red_flags"]


def test_law_court_intelligence_extracts_affirmance_and_holding():
    extractor = LawCourtIntelligenceExtractor()
    text = (
        "The father appeals a final parental rights judgment. "
        "We affirm the judgment because the court made supported best interest findings."
    )

    brief = extractor.extract_case_brief(text, source_id="source-2025-me-2", citation="2025 ME 2")

    assert brief["disposition"] == "affirmed"
    assert brief["holding"].startswith("We affirm")
    assert "parental_rights_responsibilities" in brief["issue_labels"]
