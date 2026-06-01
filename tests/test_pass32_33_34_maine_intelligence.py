from legal.drafting import DraftReviewer, Rule52BestInterestFindingsEngine
from legal.forms import FormCatalogBuilder
from legal.law_court import LawCourtIntelligenceExtractor


def test_pass32_law_court_structured_case_brief_and_appellate_red_flags():
    text = """
    Smith v. Smith
    Docket: FAM-25-12
    Decided: May 1, 2026
    In this post-judgment appeal, we review parental rights for abuse of discretion
    and findings for clear error. The court failed to make findings under Rule 52
    and did not address best interest evidence. We vacate and remand because the
    lack of findings prevents appellate review. The appellant also did not preserve
    one evidentiary argument.
    """
    brief = LawCourtIntelligenceExtractor().extract_case_brief(
        text,
        source_id="case-smith-2026",
        citation="2026 ME 99",
    )

    assert brief["caption"] == "Smith v. Smith"
    assert brief["docket_number"] == "FAM-25-12"
    assert brief["decision_date"] == "May 1, 2026"
    assert brief["standard_of_review"] == "mixed"
    assert brief["disposition"] in {"remanded", "mixed"}
    assert "Rule_52_findings" in brief["issue_labels"]
    assert "missing Rule 52 findings" in brief["appellate_red_flags"]
    assert brief["remand_reason"] is not None


def test_pass32_appellate_red_flags_feed_draft_review():
    brief = {
        "appellate_red_flags": ["missing Rule 52 findings"],
        "issue_labels": ["Rule_52_findings"],
    }
    review = DraftReviewer().review(
        {
            "caption": "Smith v. Smith",
            "facts": "Facts.",
            "requested_relief": "Relief.",
            "source_cards": [{"source_id": "case"}],
            "authority_matrix": [{"source_id": "case"}],
            "citation_report": {"status": "pass"},
            "quote_report": {"status": "pass"},
            "law_court_briefs": [brief],
            "human_review_complete": True,
        }
    )
    assert "appellate_red_flag:missing Rule 52 findings" in review["blockers"]
    assert "missing Rule 52 findings" in review["appellate_red_flags"]


def test_pass33_form_catalog_versions_required_fields_context_and_dependencies():
    records = [
        {
            "source_id": "form-fm-001",
            "form_id": "FM-001",
            "title": "FM-001 Complaint for Divorce with Children",
            "version_date": "01/2024",
            "text": "Docket Number: Plaintiff: Defendant: Child name: Signature: Depends on 19-A M.R.S. § 1653 and M.R. Civ. P. 120.",
        },
        {
            "source_id": "form-pa-001",
            "form_id": "PA-001",
            "title": "PA-001 Protection from Abuse Complaint",
            "version_date": "01/2026",
            "text": "Plaintiff: Defendant: Address: Signature:",
        },
    ]
    report = FormCatalogBuilder().build_catalog(
        records,
        current_versions={"FM-001": "01/2026", "PA-001": "01/2026"},
    )

    data = report.to_dict()
    assert data["form_count"] == 2
    assert "FM-001" in data["stale_forms"]
    fm = next(entry for entry in data["entries"] if entry["form_id"] == "FM-001")
    assert fm["filing_context"] == "family_matter"
    assert "docket_number" in fm["required_fields"]
    assert "child_name" in fm["required_fields"]
    assert "19-A M.R.S. § 1653" in fm["dependencies"]
    assert "M.R. Civ. P. 120" in fm["dependencies"]
    pfa_results = FormCatalogBuilder().search(report, filing_context="protection_from_abuse")
    assert [entry["form_id"] for entry in pfa_results] == ["PA-001"]


def test_pass34_rule52_best_interest_findings_engine_blocks_sparse_order():
    order = """
    Final order on parental rights. The prior protection from abuse order is adopted.
    Father shall have supervised contact. Primary residence is awarded to Mother.
    """
    review = Rule52BestInterestFindingsEngine().review_order(order, posture="final_order").to_dict()

    assert "findings_of_fact_section_missing" in review["missing_findings"]
    assert "contact_restriction_without_supported_findings" in review["blockers"]
    assert "pfa_family_overlap_independent_analysis_missing" in review["blockers"]
    assert "missing Rule 52 findings" in review["red_flags"]
    assert len(review["proposed_findings_checklist"]) >= 5


def test_pass34_contact_restriction_with_evidence_has_no_contact_support_blocker():
    order = """
    Findings of fact. The court finds domestic abuse evidence showed a safety risk.
    The child needs stability and school continuity. Supervised contact is ordered
    because credible testimony and Exhibit 4 show risk of harm.
    The court independently finds the PFA facts support limited contact under the family case record.
    """
    review = Rule52BestInterestFindingsEngine().review_order(order, posture="final_order").to_dict()
    assert "contact_restriction_without_supported_findings" not in review["blockers"]
    assert review["contact_restriction_report"]["support_detected"] is True
