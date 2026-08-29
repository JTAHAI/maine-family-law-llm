"""Static packaging contracts supplement, not replace, frozen-browser checks."""

from html.parser import HTMLParser
from pathlib import Path

import pytest


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("root", ["src/maine_family_law_llm/ui", "maine_family_law_llm/ui"])
def test_compatibility_metadata_is_not_screen_reader_content(root):
    html = Path(root, "workbench.html").read_text(encoding="utf-8")
    parsed = Elements()
    parsed.feed(html)
    marker = next(attrs for _, attrs in parsed.tags if attrs.get("id") == "compatibility-markers")
    assert marker["aria-hidden"] == "true" and "hidden" in marker
    images = [
        attrs for tag, attrs in parsed.tags if tag == "img" and attrs.get("class") == "sr-only"
    ]
    assert images
    assert all(attrs.get("alt") == "" and attrs.get("aria-hidden") == "true" for attrs in images)


@pytest.mark.parametrize("root", ["src/maine_family_law_llm/ui", "maine_family_law_llm/ui"])
def test_send_shortcut_matches_actual_enter_behavior(root):
    html = Path(root, "workbench.html").read_text(encoding="utf-8")
    button = html.split('id="ask-button"', 1)[1].split("</button>", 1)[0]
    assert "<small>Enter</small>" in button
    assert "Shift+Enter" not in button
    assert "<strong>Shift+Enter</strong> for a new line" in html


@pytest.mark.parametrize("root", ["src/maine_family_law_llm/ui", "maine_family_law_llm/ui"])
def test_verification_heading_overrides_dark_body_kicker_color(root):
    css = Path(root, "workbench.css").read_text(encoding="utf-8")
    assert ".authority-verification-header .source-preview-kicker { color: #d4e8f6; }" in css

    def luminance(color):
        values = [int(color[index : index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in values
        ]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    assert (luminance("d4e8f6") + 0.05) / (luminance("082d57") + 0.05) >= 4.5
