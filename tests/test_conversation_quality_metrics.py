from legal.evals.conversation_quality_metrics import ConversationQualityRegressionRunner


def test_conversation_quality_regression_metrics_pass_with_required_case_count() -> None:
    report = ConversationQualityRegressionRunner().run().as_dict()
    assert report["status"] == "pass"
    assert report["case_count"] >= 40
    assert report["hard_failures"] == []
    assert all(value == 1.0 for value in report["metrics"].values())


def test_conversation_quality_regression_loads_existing_and_extra_cases() -> None:
    assert ConversationQualityRegressionRunner().load_case_count() >= 40
