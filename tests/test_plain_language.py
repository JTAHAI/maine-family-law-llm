from legal.conversation import PlainLanguageRewriter


def test_plain_language_rewriter_adds_meaning_sections_without_claiming_filing_ready() -> None:
    rewriter = PlainLanguageRewriter()
    payload = {
        "short_answer": "The motion to modify is still review required.",
        "explanation": "The motion to modify is still review required.",
        "review_required": True,
    }
    rewritten = rewriter.rewrite_response(payload)
    assert "What this means:" in rewritten["text"]
    assert "What this does not mean:" in rewritten["text"]
    assert "filing-ready" in rewritten["text"]
