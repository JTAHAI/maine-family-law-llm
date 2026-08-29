from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass122_component_module_is_shipped_before_the_workbench_controller() -> None:
    html = (SOURCE_UI / "workbench.html").read_text(encoding="utf-8")
    components = (SOURCE_UI / "workbench_components.js").read_text(encoding="utf-8")
    controller = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")

    assert "/ui-assets/workbench_components.js?v={{UI_VERSION}}" in html
    assert html.index("workbench_components.js") < html.index("workbench.js")
    assert "MaineWorkbenchComponents" in components
    assert "filterAndGroupCommands" in components
    assert "moveListIndex" in components
    assert "MaineWorkbenchComponents" in controller
    assert "componentLibrary?.filterAndGroupCommands" in controller


def test_pass122_component_module_is_in_the_production_and_frozen_asset_contract() -> None:
    from maine_family_law_llm.production_ui import PRODUCTION_ASSETS, production_ui_manifest

    assert "workbench_components.js" in PRODUCTION_ASSETS
    manifest = production_ui_manifest(SOURCE_UI)
    assert manifest["status"] == "pass"
    assert "workbench_components.js" in manifest["assets"]
    for name in ("workbench.html", "workbench.css", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()


def test_pass122_component_primitives_are_deterministic_and_non_wrapping() -> None:
    # Unit behavior is additionally checked by Node in the focused command;
    # source-level assertions keep the Python-only suite dependency-free.
    components = (SOURCE_UI / "workbench_components.js").read_text(encoding="utf-8")
    assert "never executes a command" in components
    assert "return Math.min(Math.max(0, current + delta), count - 1);" in components
