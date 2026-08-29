"""Regression coverage for the v8 control strip's explicit desktop tracks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_v8_control_strip_uses_semantic_controls_and_no_implicit_desktop_tracks() -> None:
    html = (SOURCE_UI / "workbench.html").read_text(encoding="utf-8")
    css = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    for name in ("audience", "answer-style", "response-depth", "topic-filter", "focus-context"):
        assert f'data-control="{name}"' in html
    for name in ("command", "ai-controls", "privacy", "matter", "evidence", "help", "new-chat"):
        assert f'data-control-action="{name}"' in html

    assert "@media (min-width: 1360px) and (max-width: 1899px)" in css
    assert "grid-template-columns: repeat(12, minmax(0, 1fr));" in css
    assert "grid-template-rows: auto 40px;" in css
    assert "grid-auto-flow: row;" in css
    assert "> [data-control-action] {" in css
    assert "grid-row: 2;" in css
    assert "@media (min-width: 1900px)" in css
    assert "145px 105px 110px 145px 155px 40px 40px" in css


def test_v8_control_strip_assets_stay_identical_in_the_packaging_mirror() -> None:
    for name in ("workbench.html", "workbench.css"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
