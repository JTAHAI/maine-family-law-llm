from pathlib import Path

import pytest

import legal.conversation.product_polish_passes as polish

from legal.conversation.product_polish_passes import (
    ProductPolishReadinessAuditor,
)


@pytest.fixture(autouse=True)
def isolated_evidence(tmp_path, monkeypatch):
    paths = [polish.SUMMARY_PATH, polish.QUALITY_OUTPUT_PATH, polish.USER_JOURNEY_OUTPUT_PATH]
    before = {path: path.read_bytes() if path.exists() else None for path in paths}
    monkeypatch.setattr(polish, "ROOT", tmp_path)
    monkeypatch.setattr(polish, "QUALITY_OUTPUT_PATH", tmp_path / "quality.json")
    monkeypatch.setattr(polish, "USER_JOURNEY_OUTPUT_PATH", tmp_path / "journey.json")
    yield
    assert {path: path.read_bytes() if path.exists() else None for path in paths} == before


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


def test_product_polish_auditor_writes_eval_artifacts(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    report = ProductPolishReadinessAuditor().write(summary, run_tests=False).as_dict()
    assert summary.is_file()
    assert polish.USER_JOURNEY_OUTPUT_PATH.is_file()
    assert polish.QUALITY_OUTPUT_PATH.is_file()
    assert report["user_journey_eval_report"]["status"] == "pass"
    assert report["conversation_quality_regression"]["status"] == "pass"
