from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass126_keyboard_shortcuts_are_discoverable_allowlisted_and_locally_persisted() -> None:
    html = (SOURCE_UI / "workbench.html").read_text(encoding="utf-8")
    script = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")
    css = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    for marker in (
        'id="shortcut-command-palette"',
        'id="shortcut-justice"',
        'id="shortcut-preferences-save"',
        'data-shortcut-command-palette',
        'data-shortcut-justice',
    ):
        assert marker in html
    for marker in (
        "KEYBOARD_SHORTCUT_STORAGE_KEY",
        "keyboardShortcutOptions",
        "function keyboardShortcutMatches",
        "function saveKeyboardShortcuts",
        "Only listed local shortcuts can be saved.",
        "shortcutPreferencesSave?.addEventListener('click', saveKeyboardShortcuts)",
    ):
        assert marker in script
    assert ".shortcut-preferences" in css


def test_pass126_keyboard_command_assets_remain_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
