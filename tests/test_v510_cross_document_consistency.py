from __future__ import annotations

from legal.matter.consistency_review import SourceText, find_cross_document_conflicts


def test_conflicting_hearing_dates_are_reported_with_sources() -> None:
    sources = [
        SourceText("doc_a", "notice.pdf", "The hearing is scheduled for August 12, 2026."),
        SourceText("doc_b", "email.txt", "The hearing will occur on August 14, 2026."),
    ]
    conflicts = find_cross_document_conflicts(sources)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.context_key == "hearing_date"
    assert conflict.severity == "high"
    assert {item.filename for item in conflict.occurrences} == {"notice.pdf", "email.txt"}
    assert conflict.legal_significance == "not_determined"


def test_unrelated_dates_do_not_create_conflict() -> None:
    sources = [
        SourceText("doc_a", "order.pdf", "The order dated January 5, 2026 remains in effect."),
        SourceText("doc_b", "service.pdf", "Service was completed January 7, 2026."),
    ]
    assert find_cross_document_conflicts(sources) == ()


def test_distinct_contact_details_are_not_treated_as_conflicts() -> None:
    sources = [
        SourceText("doc_a", "parent-a.txt", "Contact Alex at alex@example.com or 207-555-0101."),
        SourceText("doc_b", "parent-b.txt", "Contact Blair at blair@example.com or 207-555-0102."),
    ]
    assert find_cross_document_conflicts(sources) == ()
