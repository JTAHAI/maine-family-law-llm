from __future__ import annotations

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers import (
    FreshnessJurisdictionTreatmentChecker,
    LegalOutputVerifier,
    SourceAuthorityIndex,
    extract_legal_claims,
)
from legal.verifiers.source_cards import SourceCardStore


def _index() -> SourceAuthorityIndex:
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-1653")
    index.add_case("2026", "1", "source-case-2026-me-1")
    index.add_form("FM-002", "source-form-fm-002")
    return index


def _metadata() -> dict[str, dict]:
    return {
        "source-statute-1653": {
            "source_id": "source-statute-1653",
            "title": "Parental rights and responsibilities",
            "citation": "19-A M.R.S. § 1653",
            "source_class": "statute_section_reference",
            "jurisdiction": "maine",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
            "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
        },
        "source-case-2026-me-1": {
            "source_id": "source-case-2026-me-1",
            "title": "Test v. Test",
            "citation": "2026 ME 1",
            "source_class": "law_court_opinion_index",
            "jurisdiction": "maine",
            "authority_status": "verified_maine_law_court",
            "freshness_status": "current",
            "negative_treatment_status": "positive_or_neutral",
        },
        "source-form-fm-002": {
            "source_id": "source-form-fm-002",
            "title": "Family Matter Summary Sheet",
            "citation": "FM-002",
            "source_class": "court_forms_index",
            "jurisdiction": "maine",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
            "form_version_status": "current",
        },
    }


def _texts() -> dict[str, str]:
    return {
        "source-statute-1653": "19-A M.R.S. § 1653 provides that parental rights and responsibilities are decided according to the best interest of the child.",
        "source-case-2026-me-1": "2026 ME 1 applied best interest findings in a parental rights appeal.",
        "source-form-fm-002": "FM-002 is the Family Matter Summary Sheet form.",
    }


def test_pass29_verifier_returns_source_card_offsets_and_pinpoint_citation_support():
    verifier = LegalOutputVerifier(_index())
    report = verifier.verify_output(
        text='Under 19-A M.R.S. § 1653, Maine uses the "best interest of the child" standard.',
        source_texts=_texts(),
        source_metadata=_metadata(),
        source_cards=SourceCardStore(_metadata().values()),
        quotes=[{"source_id": "source-statute-1653", "quoted_text": "best interest of the child"}],
    )

    citation = report["citations"][0]
    quote = report["quotes"][0]

    assert citation["status"] == "found"
    assert citation["source_card"]["source_id"] == "source-statute-1653"
    assert citation["pinpoint_support"]["supported"] is True
    assert quote["status"] == "exact_match"
    assert quote["start_offset"] is not None
    assert quote["end_offset"] > quote["start_offset"]
    assert report["filing_ready_possible"] is True


def test_pass30_claim_extraction_and_support_trace_blocks_unsupported_claims():
    claims = extract_legal_claims(
        "Maine requires best interest findings. The sky is blue. Maine requires a purple parenting certificate."
    )
    verifier = LegalOutputVerifier(_index())
    report = verifier.verify_output(
        text="Maine requires a purple parenting certificate.",
        source_texts={"source-statute-1653": _texts()["source-statute-1653"]},
        source_metadata={"source-statute-1653": _metadata()["source-statute-1653"]},
        auto_extract_claims=True,
    )

    assert "Maine requires best interest findings." in claims
    assert "claim_unsupported" in report["blockers"]
    assert report["claims"][0]["source_trace"]["best_source_id"] == "source-statute-1653"


def test_pass31_blocks_current_law_claims_from_unknown_freshness_wrong_jurisdiction_and_forms():
    checker = FreshnessJurisdictionTreatmentChecker()
    report = checker.check(
        text="Current Maine law requires use of this form.",
        source_metadata={
            "stale-statute": {
                "source_id": "stale-statute",
                "source_class": "statute_section_reference",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "unknown",
            },
            "nh-case": {
                "source_id": "nh-case",
                "source_class": "case",
                "jurisdiction": "new_hampshire",
                "authority_status": "verified_public_api",
                "freshness_status": "current",
            },
            "old-form": {
                "source_id": "old-form",
                "source_class": "court_forms_index",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "current",
                "form_version_status": "unknown",
            },
        },
    )

    assert "stale_or_unknown_freshness:stale-statute" in report["blockers"]
    assert "jurisdiction_mismatch:nh-case" in report["blockers"]
    assert "form_freshness_not_verified:old-form" in report["blockers"]
    assert report["verified"] is False


def test_pass31_filing_gate_consumes_scope_blockers():
    gate = FilingReadyGate()
    result = gate.evaluate(
        {
            "citations_verified": True,
            "quote_spans_verified": True,
            "human_review_complete": True,
            "authority_verified": True,
            "verification_report": {"blockers": ["stale_or_unknown_freshness:source-1"]},
        }
    )

    assert result["filing_ready"] is False
    assert "stale_or_unknown_freshness:source-1" in result["blockers"]
