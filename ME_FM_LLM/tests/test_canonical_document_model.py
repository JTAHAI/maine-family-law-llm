from legal.documents import SourceLocation, StatuteSection, chunk_text


def test_statute_section_source_card_and_chunk_offsets():
    section = StatuteSection(
        document_id="statute-19a-1653",
        source_location=SourceLocation(
            source_id="source-1653",
            url_or_path="https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
        ),
        document_type="statute_section",
        title="19-A M.R.S. § 1653: Parental rights and responsibilities",
        text="Best interest of the child. " * 200,
        citation="19-A M.R.S. § 1653",
        title_number="19-A",
        section_number="1653",
    )

    card = section.source_card(hash_value="abc")
    chunks = chunk_text(
        document_id=section.document_id,
        source_id=section.source_location.source_id,
        text=section.text,
        citation=section.citation,
        max_chars=300,
        overlap_chars=25,
    )

    assert card.citation == "19-A M.R.S. § 1653"
    assert chunks
    assert chunks[0].parent_document_id == section.document_id
    assert chunks[0].source_location.start_offset == 0
    assert chunks[0].validate() == []
