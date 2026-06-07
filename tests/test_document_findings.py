from legal.conversation.document_findings import DocumentFindingsExtractor


def test_document_findings_extract_citations_quotes_and_unverified_facts() -> None:
    findings = DocumentFindingsExtractor().extract('Motion to modify child support. "Quoted text here." See 19-A M.R.S. § 1653.')
    assert "child_support" in findings["issue_labels"]
    assert findings["citations_found"]
    assert findings["quotes_found"][0]["status"] == "quote_span_not_found"
    assert findings["extracted_facts"][0]["label"] == "unverified"
