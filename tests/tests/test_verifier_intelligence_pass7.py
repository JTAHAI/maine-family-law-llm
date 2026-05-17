from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers import ClaimSupportVerifier, LegalOutputVerifier, QuoteSpanVerifier, SourceAuthorityIndex
from legal.verifiers.authority_status_verifier import AuthorityStatusVerifier


def test_quote_verifier_reports_exact_fuzzy_and_missing_statuses():
    verifier = QuoteSpanVerifier()

    exact = verifier.verify("The best interest of the child standard applies.", "best interest")
    fuzzy = verifier.verify("The court must make sufficient findings.", "court must make findings")
    missing = verifier.verify("The court must make sufficient findings.", "banana citation")

    assert exact["status"] == "exact_match"
    assert fuzzy["status"] in {"fuzzy_match", "semantic_match"}
    assert missing["status"] == "quote_span_not_found"
    assert missing["verified"] is False


def test_claim_support_verifier_classifies_supported_and_unsupported_claims():
    verifier = ClaimSupportVerifier()
    source = "Parental rights and responsibilities are decided according to the best interest of the child."

    supported = verifier.verify(
        "Parental rights are decided according to the best interest of the child.",
        [source],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
    )
    unsupported = verifier.verify(
        "Maine requires a purple parenting certificate in every custody case.",
        [source],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
    )

    assert supported["status"] == "supported"
    assert supported["supported"] is True
    assert unsupported["status"] == "unsupported"
    assert unsupported["supported"] is False


def test_claim_support_verifier_flags_stale_and_jurisdiction_mismatch():
    verifier = ClaimSupportVerifier()

    stale = verifier.verify(
        "Best interest controls parental rights.",
        ["Best interest controls parental rights."],
        authority_statuses=["stale_unknown"],
        source_jurisdictions=["maine"],
    )
    mismatch = verifier.verify(
        "Best interest controls parental rights.",
        ["Best interest controls parental rights."],
        authority_statuses=["verified_public_api"],
        source_jurisdictions=["new_hampshire"],
    )

    assert stale["status"] == "stale"
    assert mismatch["status"] == "jurisdiction_mismatch"


def test_authority_status_verifier_checks_domain_freshness_and_jurisdiction():
    verifier = AuthorityStatusVerifier()

    official = verifier.verify_url("https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html")
    unknown = verifier.verify_url("https://example.com/maine-custody-summary")
    mismatch = verifier.verify_source(
        {
            "source_id": "nh-source",
            "jurisdiction": "new_hampshire",
            "authority_status": "verified_public_api",
            "freshness_status": "current",
        }
    )

    assert official.verified is True
    assert official.status == "verified_official_maine"
    assert unknown.verified is False
    assert mismatch.status == "jurisdiction_mismatch"


def test_legal_output_verifier_blocks_fake_citations_missing_quotes_and_unsupported_claims():
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-1653")
    verifier = LegalOutputVerifier(index)
    report = verifier.verify_output(
        text='19-A M.R.S. § 1653 and 99 M.R.S. § 9999 say "purple certificate".',
        source_texts={
            "source-statute-1653": "Parental rights and responsibilities use the best interest standard."
        },
        source_metadata={
            "source-statute-1653": {
                "source_id": "source-statute-1653",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "current",
            }
        },
        quotes=[{"source_id": "source-statute-1653", "quoted_text": "purple certificate"}],
        claims=[{"claim": "Maine requires a purple certificate.", "source_ids": ["source-statute-1653"]}],
    )

    assert any(blocker.startswith("citation_not_found") for blocker in report["blockers"])
    assert "quote_span_not_found:source-statute-1653" in report["blockers"]
    assert "claim_unsupported" in report["blockers"]
    assert report["filing_ready_possible"] is False


def test_filing_gate_consumes_verification_report_blockers():
    gate = FilingReadyGate()
    result = gate.evaluate(
        {
            "citations_verified": True,
            "quote_spans_verified": True,
            "human_review_complete": True,
            "authority_verified": True,
            "verification_report": {"blockers": ["claim_unsupported"]},
        }
    )

    assert result["filing_ready"] is False
    assert result["export_status"] == "blocked"
