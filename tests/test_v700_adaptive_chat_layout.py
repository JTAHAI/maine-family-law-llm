from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR = ROOT / "maine_family_law_llm" / "ui"


def _read(name: str) -> str:
    return (PRODUCTION / name).read_text(encoding="utf-8")


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(left: str, right: str) -> float:
    first, second = sorted((_relative_luminance(left), _relative_luminance(right)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def test_secondary_text_tokens_meet_wcag_aa_on_white() -> None:
    css = _read("workbench.css")
    values = dict(re.findall(r"--(muted|v5-ink-500|v5-ink-700):\s*(#[0-9a-fA-F]{6})", css))
    assert _contrast(values["muted"], "#ffffff") >= 4.5
    assert _contrast(values["v5-ink-500"], "#ffffff") >= 4.5
    assert _contrast(values["v5-ink-700"], "#ffffff") >= 4.5
    assert "opacity: 1;" in css
    assert 'input, textarea)::placeholder' in css


def test_supporting_cards_can_be_hidden_and_chat_expands() -> None:
    html = _read("workbench.html")
    css = _read("workbench.css")
    javascript = _read("workbench.js")
    assert 'id="toggle-side-cards-button"' in html
    assert 'aria-controls="workbench-shortcuts"' in html
    assert 'id="workbench-shortcuts"' in html
    assert 'body[data-shortcuts="closed"] .workbench-rail' in css
    assert 'body[data-shortcuts="closed"][data-drawer="closed"] .v5-main-stage.main-stage' in css
    assert "setShortcutCardsVisible" in javascript
    assert "mfl-workbench-layout-v1" in javascript
    assert "Shortcut cards hidden. Chat expanded." in javascript
    assert "toggle_shortcut_cards" in javascript


def test_production_and_packaging_mirror_assets_are_identical() -> None:
    for name in ("workbench.html", "workbench.css", "workbench.js"):
        assert (PRODUCTION / name).read_bytes() == (MIRROR / name).read_bytes()
