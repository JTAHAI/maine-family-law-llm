from legal.drafting.filing_ready_gate import FilingReadyGate

def test_filing_ready_gate_blocks_export():
    gate = FilingReadyGate()

    result = gate.evaluate({
        "citations_verified": True,
        "quote_spans_verified": False,
        "human_review_complete": False,
        "authority_verified": True
    })

    assert result["filing_ready"] is False
