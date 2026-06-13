from __future__ import annotations

from pathlib import Path

from maine_family_law_llm.privacy_classifier import classify_privacy


def test_privacy_classifier_excludes_personal_nonlegal_material() -> None:
    result = classify_privacy(
        "Volunteer birthday newsletter with unrelated chapter details.",
        Path("newsletter.txt"),
        "native_document",
        [],
    )
    assert "personal_nonlegal" in result["privacy_classes"]
    assert result["external_release_allowed"] is False


def test_privacy_classifier_flags_child_medical_school_sensitivity() -> None:
    result = classify_privacy(
        "Minor student school attendance, counseling session, medical provider, and MaineCare coordination.",
        Path("sensitive.txt"),
        "native_document",
        ["School records"],
    )
    assert "child_sensitive" in result["privacy_classes"]
    assert "medical_sensitive" in result["privacy_classes"]
    assert "school_sensitive" in result["privacy_classes"]
