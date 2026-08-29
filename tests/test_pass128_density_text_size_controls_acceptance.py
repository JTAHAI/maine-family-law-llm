from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass128_display_preferences_are_local_allowlisted_and_visible() -> None:
    html = (SOURCE_UI / "workbench.html").read_text(encoding="utf-8")
    script = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")
    css = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    for marker in ('id="display-density"', 'id="display-text-scale"', 'id="display-preferences-save"', 'id="display-preferences-status"'):
        assert marker in html
    for marker in (
        "DISPLAY_PREFERENCES_STORAGE_KEY",
        "displayPreferenceOptions",
        "function syncDisplayPreferences",
        "function saveDisplayPreferences",
        "dataset.density = displayPreferences.density",
        "dataset.textScale = displayPreferences.text_scale",
    ):
        assert marker in script
    for marker in (".display-preferences", 'data-density="compact"', 'data-text-scale="large"', 'data-text-scale="extra_large"'):
        assert marker in css


def test_pass128_display_preference_assets_remain_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
