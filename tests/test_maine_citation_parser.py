from legal.verifiers.citation_parser import extract_maine_statute_citations

def test_extract_statute():
    text = "See 19-A M.R.S.A. § 1653"
    results = extract_maine_statute_citations(text)

    assert len(results) == 1
    assert results[0]["title"] == "19-A"