from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pass02_version_and_msix_build_are_incremented() -> None:
    from maine_family_law_llm.version import (
        BUILD_NUMBER,
        PACKAGE_VERSION,
        UI_PASS_MARKER,
        UI_VERSION,
        VERSION,
    )

    identity_path = ROOT / "store" / "msix" / "identity.local.json"
    if not identity_path.is_file():
        identity_path = ROOT / "store" / "msix" / "identity.example.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))

    assert VERSION == "8.0.0"
    assert BUILD_NUMBER == 53
    assert PACKAGE_VERSION == "8.0.0.0"
    assert identity["package_version"] == "8.0.0.0"
    assert UI_PASS_MARKER == "v8.0.0-ga"
    assert UI_VERSION.endswith("-b53")


def test_constitutional_identity_remains_visible_and_popover_is_complete() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()

    assert "WE THE PEOPLE" in html
    assert "... establish JUSTICE ..." in html
    assert 'id="constitutional-identity"' in html
    assert 'aria-controls="constitutional-popover"' in html
    assert 'aria-describedby="constitutional-popover"' in html
    assert 'id="close-constitutional-popover"' in html
    assert 'role="dialog"' in html
    assert (
        "Justice does not belong to one institution or one profession, it belongs "
        "to the People"
    ) in html


def test_pass02_topbar_has_privacy_matter_health_commands_help_and_new_chat() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()

    for element_id in (
        "health",
        "privacy-button",
        "matter-button",
        "matter-shortcut-button",
        "command-palette-button",
        "help-button",
        "new-chat-button",
    ):
        assert f'id="{element_id}"' in html

    assert 'aria-controls="local-status-popover"' in html
    assert 'id="local-status-popover"' in html
    assert "Your family’s matter stays on this device." in html
    assert "The authority belongs to the source, not the model." in html


def test_pass02_privacy_shortcuts_and_build_overlays_are_local_and_safe() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()

    assert 'id="privacy-overlay"' in html
    assert 'id="shortcuts-overlay"' in html
    assert 'id="build-overlay"' in html
    assert 'id="footer-version"' in html
    assert "8.0.0.0" in html
    assert "This card intentionally contains no private paths" in html
    assert "does not silently send your question" in html
    assert "Every critical action remains available by mouse and touch." in html


def test_pass02_command_palette_is_grouped_complete_and_keyboard_accessible() -> None:
    from maine_family_law_llm.local_workbench_ui import read_workbench_asset

    js = read_workbench_asset("workbench.js")

    for command_id in (
        "new_conversation",
        "focus_composer",
        "research_maine_law",
        "search_my_records",
        "search_both_separately",
        "toggle_evidence_drawer",
        "open_source_list",
        "choose_matter",
        "change_answer_style",
        "open_help",
        "open_privacy_information",
        "open_keyboard_shortcuts",
        "open_justice_lens",
    ):
        assert f"id: '{command_id}'" in js

    assert "class=\"command-group\"" in js
    # Alias filtering lives in the shared production component so the
    # workbench and any future shell apply the same search semantics.
    component_js = read_workbench_asset("workbench_components.js")
    assert "candidate.aliases" in component_js
    assert "aria-activedescendant" in js
    assert "aria-posinset" in js
    assert "aria-setsize" in js
    assert "event.key === 'Home'" in js
    assert "event.key === 'End'" in js
    assert "event.key === 'Escape'" in js
    assert "we the people" in js
    assert "justice constitution" in js


def test_pass02_popovers_have_pointer_keyboard_touch_and_escape_paths() -> None:
    from maine_family_law_llm.local_workbench_ui import read_workbench_asset

    js = read_workbench_asset("workbench.js")

    assert "constitutionalIdentity?.addEventListener('mouseenter'" in js
    assert "constitutionalIdentity?.addEventListener('focus'" in js
    assert "constitutionalIdentity?.addEventListener('click'" in js
    assert "constitutionalPopover?.addEventListener('focusin'" in js
    assert "health?.addEventListener('mouseenter'" in js
    assert "health?.addEventListener('focus'" in js
    assert "health?.addEventListener('click'" in js
    assert "localStatusPopover?.addEventListener('focusin'" in js
    assert "hideConstitutionalPopover({force: true})" in js
    assert "hideLocalStatus({force: true})" in js


def test_pass02_css_preserves_visible_identity_and_accessibility_modes() -> None:
    from maine_family_law_llm.local_workbench_ui import read_workbench_asset

    css = read_workbench_asset("workbench.css")

    assert "v3.3" in css or "v3.2" in css
    assert ".topbar-popover" in css
    assert ".civic-tooltip::after" in css
    assert ".command-group" in css
    assert ".privacy-grid" in css
    assert "@media (max-width: 520px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (forced-colors: active)" in css
    assert ".justice-line" in css
    assert ".constitutional-identity .eyebrow" in css


def test_pass02_runtime_diagnostics_advertise_completed_features() -> None:
    from maine_family_law_llm.api import runtime_diagnostics

    diagnostics = runtime_diagnostics()

    assert diagnostics["constitutional_bar_pass02"] is True
    assert diagnostics["privacy_overlay"] is True
    assert diagnostics["keyboard_shortcuts_overlay"] is True
    assert diagnostics["command_palette_grouped"] is True
