from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_v3_pass01_uses_split_local_ui_assets() -> None:
    from maine_family_law_llm.local_workbench_ui import (
        read_workbench_asset,
        render_local_workbench_html,
    )

    html = render_local_workbench_html()
    css = read_workbench_asset("workbench.css")
    js = read_workbench_asset("workbench.js")

    assert "/ui-assets/workbench.css" in html
    assert "/ui-assets/workbench.js" in html
    assert "<style>" not in html
    assert "constitutional-bar" in html
    assert "evidence-drawer" in html
    assert "command-palette-button" in html
    assert "justice-overlay" in html
    assert "Ctrl K" in html
    assert "Ctrl J" in html

    assert "body[data-drawer=\"open\"] .evidence-drawer" in css
    assert "transform: translateX(calc(100% + 16px))" in css
    assert "prefers-reduced-motion" in css
    assert "forced-colors" in css

    # Shortcuts are now configurable and normalized in one matcher rather than
    # duplicated raw-key handlers.  Keep this test bound to the behavioral
    # contract without requiring the previous implementation spelling.
    assert "function keyboardShortcutMatches" in js
    assert "toLocaleLowerCase()" in js
    assert "shortcut === 'ctrl+k'" in js
    assert "shortcut === 'ctrl+j'" in js
    assert "openCommandPalette" in js
    assert "openJustice" in js
    assert "setDrawerOpen" in js
    assert "drawerReturnFocus" in js
    assert "closeDrawerButton?.focus({preventScroll: true})" in js
    assert "returnTarget.focus({preventScroll: true})" in js
    assert "sessionStorage.getItem('mfl-welcome-dismissed')" not in js


def test_v3_pass01_constitutional_identity_is_permanent_and_accessible() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()

    assert 'id="constitutional-identity"' in html
    assert 'aria-describedby="constitutional-popover"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="constitutional-popover"' in html
    assert "WE THE PEOPLE" in html
    assert "... establish JUSTICE ..." in html
    assert (
        "Justice does not belong to one institution or one profession, it belongs "
        "to the People"
    ) in html


def test_v3_pass01_settings_link_does_not_copy_private_fields() -> None:
    from maine_family_law_llm.local_workbench_ui import read_workbench_asset

    js = read_workbench_asset("workbench.js")
    start = js.index("copyLinkButton?.addEventListener")
    end = js.index("function setDrawerOpen", start)
    copy_block = js[start:end]

    assert "url.search = ''" in copy_block
    assert "searchParams.set('role'" in copy_block
    assert "searchParams.set('style'" in copy_block
    assert "searchParams.set('mode'" in copy_block
    assert "searchParams.set('q'" not in copy_block
    assert "searchParams.set('context'" not in copy_block
    assert "searchParams.set('corpus'" not in copy_block
    assert "local paths were not included" in copy_block


def test_v3_pass01_ui_asset_name_validation_rejects_traversal() -> None:
    from maine_family_law_llm.local_workbench_ui import read_workbench_asset

    with pytest.raises(ValueError, match="invalid_workbench_asset_name"):
        read_workbench_asset("../version.py")


def test_v3_pass01_local_api_serves_ui_assets_and_diagnostics() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm.api import app, runtime_diagnostics

    assert app is not None
    client = TestClient(app)

    css = client.get("/ui-assets/workbench.css")
    js = client.get("/ui-assets/workbench.js")
    justice = client.get("/ui-assets/justice-facsimile.svg")

    assert css.status_code == 200
    assert "constitutional-bar" in css.text
    assert js.status_code == 200
    assert "openCommandPalette" in js.text
    assert justice.status_code == 200
    assert "establish Justice" in justice.text

    home = client.get("/")
    assert home.status_code == 200
    assert "default-src 'self'" in home.headers["content-security-policy"]
    assert home.headers["referrer-policy"] == "no-referrer"
    assert home.headers["x-frame-options"] == "DENY"

    diagnostics = runtime_diagnostics()
    assert diagnostics["constitutional_chat_shell_v3"] is True
    assert diagnostics["split_ui_assets"] is True
    assert diagnostics["evidence_drawer_default_closed"] is False
    assert diagnostics["command_palette_shortcut"] == "Ctrl+K"
    assert diagnostics["justice_easter_egg_shortcut"] == "Ctrl+J"


def test_v3_pass01_launcher_is_task_oriented_and_versioned() -> None:
    from maine_family_law_llm.version import VERSION

    source = (ROOT / "app" / "launcher.py").read_text(encoding="utf-8")

    assert VERSION == "8.0.1"
    assert 'notebook.add(start_tab, text="Start here")' in source
    assert 'notebook.add(review_tab, text="Review & export")' in source
    assert 'notebook.add(support_tab, text="Support & tools")' in source
    assert 'text="... establish JUSTICE ..."' in source
    assert 'takefocus=True' in source
    assert 'mission_popup = tk.Toplevel(self)' in source
    assert 'text=f"v{VERSION} · local-only"' in source
    assert '"Open Local AI Chat", "open_local_ai_chat"' in source
    assert 'style_name="Primary.TButton"' in source


def test_v3_pass01_versions_are_consistent() -> None:
    from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, VERSION

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    identity_path = ROOT / "store" / "msix" / "identity.local.json"
    if not identity_path.is_file():
        identity_path = ROOT / "store" / "msix" / "identity.example.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))

    assert VERSION == "8.0.1"
    assert BUILD_NUMBER >= 24
    assert PACKAGE_VERSION == "8.0.1.0"
    assert f'version = "{VERSION}"' in pyproject
    assert identity["package_version"] == PACKAGE_VERSION
