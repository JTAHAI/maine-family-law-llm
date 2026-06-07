from legal.conversation.document_findings import DocumentFindingsExtractor
from legal.conversation.document_instruction_filter import DocumentInstructionFilter
from legal.conversation.document_review_report import DocumentReviewReportBuilder


def test_document_review_report_contains_required_sections_and_review_required() -> None:
    filtered = DocumentInstructionFilter().filter(document_text="Confidential motion to modify.", user_instruction="Review")
    findings = DocumentFindingsExtractor().extract(filtered["document_text"])
    report = DocumentReviewReportBuilder().build(filtered=filtered, findings=findings, audience="attorney")
    assert report["document_summary"]
    assert report["missing_information"]
    assert report["review_required"] is True
    assert report["document_text_is_untrusted"] is True
