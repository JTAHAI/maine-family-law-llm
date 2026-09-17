"""Exact-span safety checks; they do not establish model relevance or truth."""

from dataclasses import replace
from hashlib import sha256

import pytest

from legal.agent_runtime import ContextSource
from legal.fast_interchange.evidence_output import (
    render_verified_evidence_extracts,
    verify_selected_evidence_spans,
)


def fixture(text='The note says "request the folder"; it does not record agreement.'):
    source = ContextSource("fictional-a", "private_record", "Fictional title", text)
    row = {
        "source_id": source.source_id,
        "reference": 1,
        "start_offset": 0,
        "end_offset": len(text),
        "source_text_sha256": sha256(text.encode()).hexdigest(),
        "quote_sha256": sha256(text.encode()).hexdigest(),
        "status": "exact",
    }
    return source, row


@pytest.mark.parametrize(
    "text",
    [
        'The note says "request the folder"; it does not record agreement.',
        "A record contains reference [99], not a source-card index.",
        "A fictional café note uses “quotation marks”.\nIt includes a second line.",
    ],
)
def test_literal_quoted_bracketed_and_multiline_source_survives(text):
    source, row = fixture(text)
    report = verify_selected_evidence_spans((row,), (source,))
    assert not report["blockers"]
    assert text in render_verified_evidence_extracts(report, (source,))
    assert report["factual_claims_verified"] is False
    assert report["relevance_verified"] is False
    answer = render_verified_evidence_extracts(report, (source,))
    assert "does not check every passage or verify relevance, facts, or law" in answer
    assert "other narrative" not in answer


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference", True),
        ("reference", 0),
        ("reference", 2),
        ("start_offset", "0"),
        ("start_offset", -1),
        ("start_offset", False),
        ("end_offset", 999),
        ("end_offset", 0),
        ("end_offset", 1.1),
        ("source_id", "wrong-source"),
        ("status", "approximately"),
        ("source_text_sha256", "f" * 64),
        ("quote_sha256", "f" * 64),
        ("source_text_sha256", None),
        ("invented_text", "private canary"),
    ],
)
def test_untrusted_span_fields_never_pass(field, value):
    source, row = fixture()
    report = verify_selected_evidence_spans(({**row, field: value},), (source,))
    assert report["blockers"]
    assert report["source_spans"] == []
    assert report["partial_extracts_available"] is False
    with pytest.raises(ValueError):
        render_verified_evidence_extracts(report, (source,))


@pytest.mark.parametrize("rows", [None, [], (), ({},), (None,), ("a",)])
def test_malformed_selected_spans_are_withheld(rows):
    source, _ = fixture()
    report = verify_selected_evidence_spans(rows, (source,))
    assert report["blockers"] and not report["source_spans"]


def test_missing_duplicate_changed_and_authority_sources_are_rejected():
    source, row = fixture()
    other = replace(source, source_id="fictional-other")
    cases = [
        ((row,), (source, other)),
        ((row, row), (source,)),
        ((row,), (replace(source, text=source.text.upper()),)),
        ((row,), (replace(source, lane="legal_authority"),)),
    ]
    for rows, sources in cases:
        report = verify_selected_evidence_spans(rows, sources)
        assert report["blockers"] and not report["source_spans"]


@pytest.mark.parametrize(
    "metadata",
    [
        {"exclude_from_model": True},
        {"privacy_exclusions": "malformed"},
        {"protected_spans": [{"start_offset": 0, "end_offset": 1, "source_text_sha256": "old"}]},
    ],
)
def test_privacy_exclusions_are_rechecked_even_with_valid_hashes(metadata):
    source, row = fixture()
    report = verify_selected_evidence_spans((row,), (replace(source, metadata=metadata),))
    assert "evidence_review_sensitive_quote_withheld" in report["blockers"]
    assert not report["source_spans"]


def test_labeled_private_value_cannot_be_rendered_as_verified_excerpt():
    source, row = fixture("Account: fictional-private-canary-442.")
    report = verify_selected_evidence_spans((row,), (source,))
    assert "evidence_review_sensitive_quote_withheld" in report["blockers"]
