from legal.connectors.maine_revisor import (
    infer_revisor_freshness,
    parse_revisor_section_html,
    parse_revisor_title_index,
)

TITLE_FIXTURE = """
<html><body>
<h1>Title 19-A: DOMESTIC RELATIONS</h1>
<p>Chapter 55: RIGHTS AND RESPONSIBILITIES §1651 - §1659</p>
<a href="title19-Asec1653.html">§1653. Parental rights and responsibilities</a>
<p>Data for this page extracted on 10/20/2025 14:32:56.</p>
</body></html>
"""

SECTION_FIXTURE = """
<html><body>
<h1>Title 19-A: DOMESTIC RELATIONS</h1>
<h2>§1653. Parental rights and responsibilities</h2>
<p>1. Legislative findings and purpose. The Legislature finds...</p>
<p>3. Best interest of child. The court shall consider...</p>
<p>Data for this page extracted on 10/20/2025 14:32:56.</p>
</body></html>
"""


def test_revisor_title_index_parser_extracts_sections_and_freshness():
    doc, audit = parse_revisor_title_index(
        TITLE_FIXTURE,
        source_id="source-title-19a",
        url="https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
    )

    assert audit.status == "parsed"
    assert doc.title_number == "19-A"
    assert doc.data_extracted_at == "10/20/2025 14:32:56"
    assert doc.retrieved_freshness_status == "known_extracted_timestamp"
    assert doc.section_links[0]["section"] == "1653"
    assert doc.chapters[0]["chapter"] == "55"


def test_revisor_section_parser_preserves_statutory_citation():
    doc, audit = parse_revisor_section_html(
        SECTION_FIXTURE,
        source_id="source-1653",
        url="https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
    )

    assert audit.status == "parsed"
    assert doc.section_number == "1653"
    assert doc.official_citation == "19-A M.R.S. § 1653"
    assert "Parental rights" in doc.title
    assert doc.source_card().citation == "19-A M.R.S. § 1653"


def test_revisor_freshness_unknown_when_timestamp_absent():
    status, extracted_at = infer_revisor_freshness("<html>No date</html>")

    assert status == "unknown"
    assert extracted_at is None
