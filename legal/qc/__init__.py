"""Independent QC issue contracts for review-required legal work product.

The role separation and triage taxonomy are adapted from the MIT-licensed
A-market ECM lawyer plugin by zeweihan and contributors.
"""

from .contracts import (
    QCDisposition,
    QCIssue,
    QCIssueClass,
    QCReport,
    build_qc_report,
)

__all__ = [
    "QCDisposition",
    "QCIssue",
    "QCIssueClass",
    "QCReport",
    "build_qc_report",
]
