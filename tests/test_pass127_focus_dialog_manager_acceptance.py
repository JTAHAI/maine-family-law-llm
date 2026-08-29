from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass127_dialog_manager_tracks_the_topmost_overlay_and_restores_its_parent() -> None:
    script = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")

    for marker in (
        "const overlayStack = [];",
        "function activeManagedOverlay()",
        "function setOverlayBackgroundState(element, active)",
        "if (!overlayStack.includes(element)) overlayStack.push(element);",
        "setOverlayBackgroundState(previous, false);",
        "const stackIndex = overlayStack.lastIndexOf(element);",
        "if (previous) setOverlayBackgroundState(previous, true);",
        "const activeOverlay = activeManagedOverlay();",
    ):
        assert marker in script
    assert "element.inert = !active;" in script
    assert "dialog.setAttribute('aria-modal', active ? 'true' : 'false');" in script


def test_pass127_focus_dialog_assets_remain_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()
