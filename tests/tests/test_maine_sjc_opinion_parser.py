from legal.connectors.maine_sjc_opinions import parse_law_court_opinion_index


HTML = """
<html><body>
<h1>2025 Published Opinions</h1>
<a href="/courts/sjc/lawcourt/2025/25me001.pdf">2025 ME 1 Smith v. Jones</a>
<a href="/courts/sjc/lawcourt/2025/25me002.pdf">FAM-24-123 Doe v. Doe 1/15/2025</a>
</body></html>
"""


def test_law_court_opinion_index_parser_extracts_pdf_references():
    opinions, audit = parse_law_court_opinion_index(
        HTML,
        source_id="lawcourt-2025",
        url="https://www.courts.maine.gov/courts/sjc/lawcourt/2025/index.html",
    )

    assert audit.status == "parsed"
    assert len(opinions) == 2
    assert opinions[0].href.endswith("25me001.pdf")
    assert opinions[0].validate() == []
    assert opinions[1].docket_number == "FAM-24-123"
