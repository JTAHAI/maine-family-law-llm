from __future__ import annotations

from legal.drafting.draft_generator import DraftGenerator
from legal.drafting.draft_reviewer import DraftReviewer
from legal.drafting.filing_ready_gate import FilingReadyGate


def test_review_required_draft_carries_source_cards_and_blocks_export_until_reports_exist():
    draft = DraftGenerator().generate_review_required_draft(
        template_id="motion",
        issue_type="child_support",
        facts=[{"fact": "The child moved on 01/03/2026."}],
        authorities=[
            {
                "source_id": "me-title-19a-2001",
                "citation": "19-A M.R.S. § 2001",
                "authority_status": "verified_official_maine",
                "score": 1.0,
            }
        ],
        requested_relief="Modify child support after review.",
    )

    assert draft["review_required"] is True
    assert draft["filing_ready"] is False
    assert draft["source_cards"]
    assert draft["authority_matrix"][0]["authority_status"] == "verified_official_maine"

    review = DraftReviewer().review(draft)
    assert "citation_report_missing" in review["blockers"]
    assert "quote_report_missing" in review["blockers"]
    assert "human_review_complete" in review["blockers"]
    assert review["filing_ready"] is False


def test_filing_gate_blocks_review_required_draft_even_with_authority():
    result = FilingReadyGate().evaluate(
        {
            "citations_verified": True,
            "quote_spans_verified": True,
            "authority_verified": True,
            "claims_supported": True,
            "citation_support_verified": True,
            "jurisdiction_verified": True,
            "form_freshness_verified": True,
            "facts_verified": True,
            "human_review_complete": False,
            "review_required": True,
        }
    )

    assert result["filing_ready"] is False
    assert "human_review_complete" in result["blockers"]
    assert result["export_status"] == "blocked"
