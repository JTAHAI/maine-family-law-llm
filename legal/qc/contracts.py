from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Iterable


class QCIssueClass(StrEnum):
    BLOCKER = "blocker"
    VERIFY = "verify"
    EVIDENCE_REQUIRED = "evidence_required"
    AUTHORITY_REQUIRED = "authority_required"
    STALE_LAW_RISK = "stale_law_risk"
    CONTRADICTED = "contradicted"
    SUGGESTION = "suggestion"


class QCDisposition(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    REJECTED = "rejected"


@dataclass(frozen=True)
class QCIssue:
    issue_id: str
    issue_class: QCIssueClass
    summary: str
    location: str
    source_ids: tuple[str, ...] = ()
    proposed_action: str = "human_review"
    disposition: QCDisposition = QCDisposition.OPEN
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issue_class"] = self.issue_class.value
        payload["disposition"] = self.disposition.value
        payload["source_ids"] = list(self.source_ids)
        return payload


@dataclass(frozen=True)
class QCReport:
    report_id: str
    draft_id: str
    drafter_run_id: str
    reviewer_run_id: str
    issues: tuple[QCIssue, ...]
    human_signoff_required: bool = True
    review_required: bool = True
    filing_ready: bool = False

    def __post_init__(self) -> None:
        if not self.drafter_run_id or not self.reviewer_run_id:
            raise ValueError("drafter and reviewer run IDs are required")
        if self.drafter_run_id == self.reviewer_run_id:
            raise ValueError("independent QC requires a distinct reviewer run")
        if self.filing_ready:
            raise ValueError("QC reports cannot mark work filing-ready")

    @property
    def blockers(self) -> tuple[QCIssue, ...]:
        blocking_classes = {
            QCIssueClass.BLOCKER,
            QCIssueClass.EVIDENCE_REQUIRED,
            QCIssueClass.AUTHORITY_REQUIRED,
            QCIssueClass.STALE_LAW_RISK,
            QCIssueClass.CONTRADICTED,
        }
        return tuple(
            issue
            for issue in self.issues
            if issue.issue_class in blocking_classes and issue.disposition == QCDisposition.OPEN
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "qc_issue_report_v1",
            "report_id": self.report_id,
            "draft_id": self.draft_id,
            "drafter_run_id": self.drafter_run_id,
            "reviewer_run_id": self.reviewer_run_id,
            "issues": [issue.to_dict() for issue in self.issues],
            "open_blocker_count": len(self.blockers),
            "human_signoff_required": self.human_signoff_required,
            "review_required": self.review_required,
            "filing_ready": self.filing_ready,
        }


def build_qc_report(
    *,
    report_id: str,
    draft_id: str,
    drafter_run_id: str,
    reviewer_run_id: str,
    issues: Iterable[QCIssue],
) -> QCReport:
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (item.issue_class.value, item.location, item.issue_id),
        )
    )
    return QCReport(
        report_id=report_id,
        draft_id=draft_id,
        drafter_run_id=drafter_run_id,
        reviewer_run_id=reviewer_run_id,
        issues=ordered,
    )
