"""Responsive and accessibility hardening for the v5 premium workbench."""

from __future__ import annotations

from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def test_v500_app_shell_uses_dynamic_viewport_without_row_gaps() -> None:
    css = read_workbench_asset("workbench.css")
    assert "height: 100dvh" in css
    assert ".v5-workbench.app-shell" in css
    assert "gap: 0" in css
    assert "overscroll-behavior: contain" in css


def test_v500_responsive_layout_has_full_compact_and_overlay_modes() -> None:
    css = read_workbench_asset("workbench.css")
    for marker in (
        "@media (min-width: 1360px)",
        "@media (max-width: 1359px)",
        "@media (max-width: 959px)",
        "@media (max-width: 719px)",
        "@media (max-width: 479px)",
        "@media (max-height: 760px) and (max-width: 959px)",
        "@media (prefers-reduced-motion: reduce)",
        "@media (forced-colors: active)",
    ):
        assert marker in css
    assert "body.drawer-modal-open" in css
    assert ".evidence-drawer[hidden]" in css


def test_v500_drawer_state_tracks_resize_and_user_preference() -> None:
    js = read_workbench_asset("workbench.js")
    for marker in (
        "let drawerUserPreference = typeof savedLayoutPreferences.evidenceOpen === 'boolean'",
        "mfl-workbench-layout-v1",
        "function currentResponsiveLayoutMode()",
        "function syncResponsiveLayout({initial = false} = {})",
        "window.matchMedia('(min-width: 960px)')",
        "window.matchMedia('(min-width: 1360px)')",
        "evidenceDrawer.hidden = !open",
        "drawer-modal-open",
        "window.addEventListener('resize', scheduleResponsiveSync",
    ):
        assert marker in js
    assert "window.matchMedia('(min-width: 1041px)')" not in js


def test_v500_mobile_keeps_settings_accessible_without_horizontal_control_overflow() -> None:
    css = read_workbench_asset("workbench.css")
    assert ".v5-control-bar .v5-control-field" in css
    assert ".v5-control-bar .v5-command-button { display: none !important; }" in css
    assert ".v5-control-bar .v5-evidence-button { grid-column: 1 / -1; }" in css
    html = render_local_workbench_html()
    assert 'id="welcome-button"' in html
    assert 'id="privacy-button"' in html
    assert 'id="matter-button"' in html
    assert 'id="focus-mode-button"' in html
    assert 'data-layout="full"' in html
    assert 'role="complementary"' in html


def test_v500_asset_copies_are_identical() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for name in ("workbench.css", "workbench.html", "workbench.js"):
        assert (root / "src/maine_family_law_llm/ui" / name).read_bytes() == (
            root / "maine_family_law_llm/ui" / name
        ).read_bytes()
