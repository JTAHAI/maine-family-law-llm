from __future__ import annotations

from legal.product.filing_gate_studio_v203 import (
    VERSION,
    build_review_packet,
    build_sample_packet,
    parse_citations,
    render_html_packet,
    sample_source_cards,
)


def test_v203_parse_maine_citations() -> None:
    cites = parse_citations("See 19-A M.R.S. § 1653, M.R. Civ. P. 52, 2024 ME 1, FM-001, and 25 U.S.C. § 1901.")
    canonical = {row["canonical_citation"] for row in cites}
    assert "19-A M.R.S. § 1653" in canonical
    assert "M.R. Civ. P. 52" in canonical
    assert "2024 ME 1" in canonical
    assert "FM-001" in canonical
    assert "25 U.S.C. § 1901" in canonical


def test_v203_sample_packet_blocks_filing_ready() -> None:
    packet = build_sample_packet()
    gate = packet["gate_report"]
    assert packet["version"] == VERSION
    assert gate["filing_ready"] is False
    assert gate["review_required"] is True
    categories = {row["category"] for row in gate["blockers"]}
    assert "citation_verification" in categories
    assert "claim_support" in categories
    assert "form_freshness" in categories
    assert "human_review" in categories
    assert packet["export_options"]["filing_ready"] == "blocked"


def test_v203_clean_reviewed_packet_can_pass_gate_when_all_inputs_verified() -> None:
    draft = (
        "This reviewed proposed order addresses best interest under 19-A M.R.S. § 1653. "
        "The review covers child age and needs, relationship with each parent, stability, safety, abuse, "
        "child preference when relevant, cooperation and contact, school and community, and medical needs. "
        "The source says \"Canonical citation marker: 19-A M.R.S. § 1653\"."
    )
    packet = build_review_packet(
        draft,
        source_cards=sample_source_cards(),
        fact_evidence=[],
        forms_used=[{"form_id": "FM-001", "freshness_status": "fresh"}],
        human_review_completed=True,
        intended_export="filing_ready",
        matter_posture="final_order",
    )
    gate = packet["gate_report"]
    assert gate["filing_ready"] is True
    assert gate["status"] == "pass"
    assert gate["blockers"] == []
    assert packet["export_options"]["filing_ready"] == "allowed_only_when_gate_passes"


def test_v203_quote_and_claim_drilldown_surfaces_reports() -> None:
    packet = build_sample_packet()
    gate = packet["gate_report"]
    assert gate["quote_report"]
    assert gate["claim_support_report"]
    assert any(row["status"] == "quote_span_found" for row in gate["quote_report"])
    assert any(row["status"].startswith("unsupported") for row in gate["claim_support_report"])


def test_v203_html_packet_contains_blocker_status() -> None:
    html = render_html_packet(build_sample_packet())
    assert "Filing Gate Studio" in html
    assert "filing_ready=False" in html
    assert "review_required=True" in html
