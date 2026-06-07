from pathlib import Path

from legal.conversation.product_polish_passes import (
    ProductPolishReadinessAuditor,
    QUALITY_OUTPUT_PATH,
    USER_JOURNEY_OUTPUT_PATH,
)


def test_product_polish_auditor_reports_47i_through_47t_complete_without_ga_claims() -> None:
    report = ProductPolishReadinessAuditor().audit(run_tests=False).as_dict()
    assert report["status"] == "pass"
    assert report["completed_internal_passes"] == [
        "47I",
        "47J",
        "47K",
        "47L",
        "47M",
        "47N",
        "47O",
        "47P",
        "47Q",
        "47R",
        "47S",
        "47T",
    ]
    assert report["remaining_true_ga_passes"] == [48, 49, 50, 51]
    assert report["does_not_reduce_true_ga_count"] is True
    assert report["emails_sent"] is False
    assert report["outreach_complete"] is False
    assert report["attorney_reviewed"] is False
    assert report["production_legal_ready"] is False


def test_product_polish_auditor_writes_eval_artifacts() -> None:
    report = ProductPolishReadinessAuditor().write(run_tests=False).as_dict()
    assert Path(USER_JOURNEY_OUTPUT_PATH).is_file()
    assert Path(QUALITY_OUTPUT_PATH).is_file()
    assert report["user_journey_eval_report"]["status"] == "pass"
    assert report["conversation_quality_regression"]["status"] == "pass"
