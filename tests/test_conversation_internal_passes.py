from pathlib import Path

import pytest

import legal.conversation.internal_passes as internal

from legal.conversation.internal_passes import (
    ConversationPilotReadinessAuditor,
)


@pytest.fixture(autouse=True)
def isolated_evidence(tmp_path, monkeypatch):
    paths = [internal.SUMMARY_PATH, internal.EVAL_OUTPUT_PATH]
    before = {path: path.read_bytes() if path.exists() else None for path in paths}
    monkeypatch.setattr(internal, "ROOT", tmp_path)
    monkeypatch.setattr(internal, "EVAL_OUTPUT_PATH", tmp_path / "eval.json")
    yield
    assert {path: path.read_bytes() if path.exists() else None for path in paths} == before


def test_conversation_internal_pass_auditor_reports_all_internal_passes_complete() -> None:
    report = ConversationPilotReadinessAuditor().audit(run_tests=False).as_dict()
    assert report["status"] == "pass"
    assert report["completed_internal_passes"] == ["47A", "47B", "47C", "47D", "47E", "47F", "47G", "47H"]
    assert report["remaining_true_ga_passes"] == [48, 49, 50, 51]
    assert report["does_not_reduce_true_ga_count"] is True
    assert report["attorney_reviewed"] is False
    assert report["ga_shipped"] is False


def test_conversation_internal_pass_auditor_writes_eval_artifact(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    report = ConversationPilotReadinessAuditor().write(summary, run_tests=False).as_dict()
    assert summary.is_file()
    assert internal.EVAL_OUTPUT_PATH.is_file()
    assert report["conversation_eval_report"]["status"] == "pass"
