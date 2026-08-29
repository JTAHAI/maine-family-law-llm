from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass123_source_cards_use_a_bounded_window_with_explicit_continuation() -> None:
    components = (SOURCE_UI / "workbench_components.js").read_text(encoding="utf-8")
    controller = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")
    styles = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    assert "function filterAndWindowItems" in components
    assert "visibleItems: matchingItems.slice(0, requestedLimit)" in components
    assert "sourceCardWindowPageSize = 60" in controller
    assert "filterAndWindowItems(" in controller
    assert "data-show-more-sources" in controller
    assert "source-card-window" in styles


def test_pass123_windowed_source_assets_are_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
