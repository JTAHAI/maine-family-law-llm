from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass124_responsive_profiles_preserve_the_chat_and_workspace_handoff() -> None:
    script = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")
    css = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    assert "function syncViewportContract()" in script
    assert "dataset.viewportProfile = profile" in script
    assert "window.visualViewport?.width || window.innerWidth" in script
    assert "Chat and its primary action remain available" in script
    assert "@media (max-width: 959px)" in css
    assert 'data-viewport-profile="overlay"' in css
    assert "min-inline-size: 44px" in css
    assert "min-block-size: 40px" in css


def test_pass124_responsive_assets_remain_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
