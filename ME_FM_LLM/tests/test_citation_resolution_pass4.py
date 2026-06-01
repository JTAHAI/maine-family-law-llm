from legal.verifiers import SourceAuthorityIndex, extract_citations


def test_parser_extracts_multiple_citation_kinds():
    text = "See 19-A M.R.S.A. § 1653, M.R. Civ. P. 120, FM-002, 42 U.S.C. § 651, and 2025 ME 1."
    citations = extract_citations(text)
    kinds = {citation.kind for citation in citations}

    assert {
        "maine_statute",
        "maine_rule",
        "maine_form",
        "federal_statute",
        "maine_case",
    } <= kinds


def test_real_citations_resolve_to_source_ids_and_fake_citation_does_not():
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-19a-1653")
    index.add_case("2025", "1", "source-lawcourt-2025-me-1")
    index.add_rule("M.R. Civ. P. 120", "source-rule-120")
    index.add_form("FM-002", "source-form-fm-002")

    resolutions = index.resolve_text(
        "19-A M.R.S. § 1653; 99 M.R.S. § 9999; 2025 ME 1; M.R. Civ. P. 120; FM-002"
    )
    by_normalized = {resolution.citation.normalized: resolution for resolution in resolutions}

    assert by_normalized["19-A M.R.S. § 1653"].source_id == "source-statute-19a-1653"
    assert by_normalized["2025 ME 1"].authority_status == "verified_maine_law_court"
    assert by_normalized["99 M.R.S. § 9999"].status == "not_found"
    assert by_normalized["FM-002"].source_id == "source-form-fm-002"
