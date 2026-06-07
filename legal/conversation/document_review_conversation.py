from __future__ import annotations

from typing import Any

from legal.conversation.document_findings import DocumentFindingsExtractor
from legal.conversation.document_instruction_filter import DocumentInstructionFilter
from legal.conversation.document_review_report import DocumentReviewReportBuilder


class DocumentReviewConversation:
    def __init__(self) -> None:
        self.filter = DocumentInstructionFilter()
        self.findings = DocumentFindingsExtractor()
        self.report = DocumentReviewReportBuilder()

    def review(self, *, document_text: str, user_instruction: str = "", audience: str = "unknown") -> dict[str, Any]:
        filtered = self.filter.filter(document_text=document_text, user_instruction=user_instruction)
        findings = self.findings.extract(filtered["document_text"])
        return self.report.build(filtered=filtered, findings=findings, audience=audience)
