from __future__ import annotations

import pytest

from legal.qc import QCIssue, QCIssueClass, QCReport, build_qc_report


def test_qc_report_enforces_independent_run_and_blockers() -> None:
    issue = QCIssue(
        issue_id="q1",
        issue_class=QCIssueClass.AUTHORITY_REQUIRED,
        summary="The proposition lacks a verified authority source.",
        location="draft:paragraph-4",
    )
    report = build_qc_report(
        report_id="qc1",
        draft_id="draft1",
        drafter_run_id="run_draft",
        reviewer_run_id="run_qc",
        issues=[issue],
    )
    assert len(report.blockers) == 1
    assert report.to_dict()["filing_ready"] is False


def test_same_run_cannot_self_approve() -> None:
    with pytest.raises(ValueError, match="distinct reviewer"):
        QCReport(
            report_id="qc1",
            draft_id="draft1",
            drafter_run_id="same",
            reviewer_run_id="same",
            issues=(),
        )
