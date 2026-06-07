from app.services.user_journey_adapter import UserJourneyAdapter


def test_user_journey_adapter_marks_demo_ready_without_counting_for_ga() -> None:
    summary = UserJourneyAdapter().summary()
    assert summary["status"] == "pass"
    assert summary["case_count"] >= 15
    assert summary["ready_for_reviewer_demo"] is True
    assert summary["does_not_count_for_ga"] is True
