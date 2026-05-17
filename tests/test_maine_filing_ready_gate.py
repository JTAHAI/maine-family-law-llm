from legal.drafting.filing_ready_gate import FilingReadyGate

def test_gate_blocks():
    gate = FilingReadyGate()

    result = gate.evaluate({
        "authority_verified": False,
        "quotes_verified": False,
        "citations_verified": False,
        "human_review_complete": False,
    })

    assert result["filing_ready"] is False