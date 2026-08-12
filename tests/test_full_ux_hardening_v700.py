from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def _read(name: str) -> str:
    return (SOURCE_UI / name).read_text(encoding="utf-8")


def test_workbench_has_one_main_landmark_and_keyboard_skip_target() -> None:
    html = _read("workbench.html")

    assert html.count("<main") == 1
    assert 'id="main-workbench"' in html
    assert 'class="skip-link" href="#main-workbench"' in html
    assert 'tabindex="-1"' in html


def test_every_static_button_has_an_explicit_non_submit_type() -> None:
    html = _read("workbench.html")
    js = _read("workbench.js")
    buttons = re.findall(r"<button\b[^>]*>", html + js, flags=re.IGNORECASE)

    assert buttons
    assert all(re.search(r'\btype="button"', button, flags=re.IGNORECASE) for button in buttons)


def test_recovery_filter_and_accessibility_controls_are_shipped() -> None:
    html = _read("workbench.html")
    js = _read("workbench.js")
    css = _read("workbench.css")

    assert 'id="connection-banner"' in html
    assert 'id="connection-retry"' in html
    assert 'id="record-card-filter-status"' in html
    assert "function checkLocalService" in js
    assert "function applyRecordCardFilter" in js
    assert "if (!question.value.trim()) question.value = text;" in js
    assert "requestAbortReason = 'service_disconnected'" in js
    assert "Local service disconnected. Your draft was restored." in js
    assert "chatPanel?.setAttribute('aria-busy', 'true')" in js
    assert "!node.closest('[hidden]')" in js
    assert ".connection-banner" in css
    assert 'body.v6-workbench[data-motion="reduced"]' in css
    assert 'body.v6-workbench[data-screen-reader-mode="true"]' in css
    assert "backdrop-filter: none" in css


def test_source_and_runtime_ui_mirrors_are_byte_identical() -> None:
    for name in ("workbench.html", "workbench.js", "workbench.css"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
