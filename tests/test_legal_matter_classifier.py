from __future__ import annotations

from pathlib import Path

from maine_family_law_llm.legal_matter_classifier import classify_legal_matter


def test_legal_matter_classifier_assigns_issue_lanes() -> None:
    result = classify_legal_matter(
        "Shared parental rights, school attendance, therapy scheduling, and MaineCare records access.",
        Path("school_and_medical.txt"),
        "native_document",
    )
    assert result["legal_score"] > 0
    assert "Shared parental rights" in result["issue_lanes"]
    assert "School records" in result["issue_lanes"]
    assert "Therapy/counseling records" in result["issue_lanes"]


def test_promotional_content_does_not_become_legal_matter() -> None:
    result = classify_legal_matter(
        "Volunteer newsletter and unrelated chapter board recruitment.",
        Path("newsletter.txt"),
        "native_document",
    )
    assert result["legal_score"] == 0
    assert result["external_release_allowed"] is False
