from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "pfa-family-case-overlap.md"


def test_pfa_family_case_overlap_explainer_exists_and_covers_core_flags() -> None:
    text = DOC.read_text(encoding="utf-8")

    required_phrases = [
        "independent-analysis concerns",
        "independent of, or joined with",
        "not binding in a separate parental-rights case",
        "determined de novo",
        "What the system should flag",
        "Reviewer checklist",
        "Title 19-A, section 1653",
        "Title 19-A, section 4110",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_pfa_family_case_overlap_explainer_is_linked_from_guides() -> None:
    guide_paths = [
        ROOT / "docs" / "user-guide.md",
        ROOT / "docs" / "reviewer-guide.md",
        ROOT / "docs" / "attorney-reviewer-guide.md",
    ]

    for guide_path in guide_paths:
        assert "pfa-family-case-overlap.md" in guide_path.read_text(encoding="utf-8")
