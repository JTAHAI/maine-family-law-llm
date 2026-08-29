import pytest

from legal.retrieval.authority_gap_detector import AuthorityGapDetector


def test_gap_detector_fails_closed_for_missing_classes_and_stale_sources() -> None:
    report = AuthorityGapDetector().review(
        [
            {"source_class": "statute_section", "freshness_status": "fresh"},
            {"source_class": "court_rule", "freshness_status": "stale"},
        ],
        issue="parental rights",
    )

    assert report["status"] == "needs_review"
    assert report["missing_material_source_classes"] == ["opinion", "form"]
    assert "freshness_review_required" in report["blockers"]
    assert report["completeness_determined"] is False


@pytest.mark.parametrize(
    "freshness", ["parser_failed", "pending", "CURRENT", "   ", "unrecognized"]
)
def test_gap_detector_blocks_every_non_fresh_state(freshness: str) -> None:
    rows = [
        {"source_class": name, "freshness_status": "fresh"}
        for name in ("statute_section", "court_rule", "law_court_opinion", "court_form")
    ]
    rows[0]["freshness_status"] = freshness

    result = AuthorityGapDetector().review(rows)

    assert result["status"] == "needs_review"
    assert "freshness_review_required" in result["blockers"]
    assert result["review_required"] is True


def test_gap_detector_does_not_infer_classes_from_substrings() -> None:
    result = AuthorityGapDetector().review(
        [{"source_class": "not_statute_rule_opinion_form", "freshness_status": "fresh"}]
    )

    assert result["missing_material_source_classes"] == ["statute", "rule", "opinion", "form"]
    assert "source_class_review_required" in result["blockers"]


def test_gap_detector_observed_metadata_is_not_current_law_or_issue_coverage() -> None:
    result = AuthorityGapDetector().review(
        (
            {"source_class": name, "freshness_status": " FRESH "}
            for name in (
                "statute_section",
                "court_rules_pdf",
                "law_court_opinion_pdf",
                "court_form_text",
            )
        ),
        issue="Fictional demonstration label",
    )

    assert result["status"] == "metadata_coverage_observed"
    assert result["freshness_counts"] == {"fresh": 4}
    assert result["review_scope"] == "active_corpus_metadata"
    assert result["issue_filter_applied"] is False
    assert result["current_law_determined"] is False
