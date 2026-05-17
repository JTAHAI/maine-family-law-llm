from legal.verifiers.quote_span_verifier import QuoteSpanVerifier

def test_quote_span_verifier():
    verifier = QuoteSpanVerifier()

    result = verifier.verify(
        "The best interest of the child standard applies.",
        "best interest of the child"
    )

    assert result["verified"] is True
