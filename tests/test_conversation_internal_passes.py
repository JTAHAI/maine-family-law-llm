from pathlib import Path

from legal.conversation.internal_passes import (
    ConversationPilotReadinessAuditor,
    EVAL_OUTPUT_PATH,
)


def test_conversation_internal_pass_auditor_reports_all_internal_passes_complete() -> None:
    report = ConversationPilotReadinessAuditor().audit(run_tests=False).as_dict()
    assert report["status"] == "pass"
    assert report["completed_internal_passes"] == ["47A", "47B", "47C", "47D", "47E", "47F", "47G", "47H"]
    assert report["remaining_true_ga_passes"] == [48, 49, 50, 51]
    assert report["does_not_reduce_true_ga_count"] is True
    assert report["attorney_reviewed"] is False
    assert report["ga_shipped"] is False


def test_conversation_internal_pass_auditor_writes_eval_artifact() -> None:
    report = ConversationPilotReadinessAuditor().write(run_tests=False).as_dict()
    assert Path(EVAL_OUTPUT_PATH).is_file()
    assert report["conversation_eval_report"]["status"] == "pass"
