from legal.authority_store.authority_layer import ParsedAuthorityRecord, _record_pinpoints
from legal.verifiers.citation_resolver import SourceAuthorityIndex


def test_pdf_replacement_paragraph_markers_create_exact_case_pinpoints() -> None:
    text = "2026 ME 1\nHeader [\ufffd1] Exact first paragraph. [\ufffd2] Exact second paragraph."
    record = ParsedAuthorityRecord.from_row(
        {
            "record_id": "opinion-1",
            "source_id": "snapshot-1",
            "source_class": "law_court_opinion_pdf",
            "authority_kind": "law_court_opinion",
            "jurisdiction": "maine",
            "citation": "2026 ME 1",
            "text": text,
            "source_span": {"start_offset": 0, "end_offset": len(text)},
        }
    )

    pinpoints = _record_pinpoints(record)

    assert [item[2]["pinpoint"] for item in pinpoints] == ["2026 ME 1, ¶ 1", "2026 ME 1, ¶ 2"]
    for _kind, _normalized, metadata in pinpoints:
        start = metadata["source_span"]["start_offset"]
        end = metadata["source_span"]["end_offset"]
        assert text[start:end].startswith("[\ufffd")


def test_duplicate_case_rows_do_not_expose_a_bare_source_span_as_a_pinpoint() -> None:
    index = SourceAuthorityIndex()
    index.add(
        kind="maine_case",
        normalized_citation="2026 me 1",
        source_id="opinion-1",
        metadata={"source_span": {"start_offset": 0, "end_offset": 50}},
    )
    index.add(
        kind="maine_case",
        normalized_citation="2026 me 1",
        source_id="opinion-1",
        metadata={
            "pinpoint": "2026 ME 1, \u00b6 1",
            "paragraph": "1",
            "source_span": {"start_offset": 5, "end_offset": 30},
        },
    )

    rows = index.to_rows()

    assert rows[0]["metadata"]["exact_pinpoints"] == [
        {
            "pinpoint": "2026 ME 1, \u00b6 1",
            "paragraph": "1",
            "source_span": {"start_offset": 5, "end_offset": 30},
        }
    ]


def test_direct_rule_pdf_outranks_empty_rule_text_reference() -> None:
    index = SourceAuthorityIndex()
    index.add(
        kind="maine_rule",
        normalized_citation="M.R. Civ. P. 52",
        source_id="rule-empty-reference",
        metadata={"source_class": "court_rule_text", "freshness_status": "fresh"},
    )
    index.add(
        kind="maine_rule",
        normalized_citation="M.R. Civ. P. 52",
        source_id="rule-direct-pdf",
        metadata={"source_class": "court_rule_pdf", "freshness_status": "fresh"},
    )

    rows = index.to_rows()

    assert [row["source_id"] for row in rows] == ["rule-direct-pdf", "rule-empty-reference"]
