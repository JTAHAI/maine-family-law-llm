from __future__ import annotations


def test_v186_workbench_matches_requested_classic_desktop_layout_markers() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "Maine Family Law LLM — FOCAF Research Workbench" in html
    assert 'class="desktop-shell classic-desktop-shell"' in html
    assert 'class="window-titlebar"' in html
    assert 'class="menubar"' in html
    assert 'class="hero-band"' in html
    assert 'class="control-strip"' in html
    assert 'class="workspace-grid"' in html
    assert 'Research Chat — Your FOCAF Assistant' in html
    assert 'FOCAF Sidebar' in html
    assert 'Prompt Shortcuts' in html
    assert 'Question Starters' in html
    assert 'Starter Packs' in html
    assert 'Recent Sources' in html
    assert 'Latest Answer' in html
    assert 'Transcript / Handoff' in html
    assert 'FOCAF Secure Connection' in html
    assert 'UI v1.87 classic desktop FOCAF research workbench' in html


def test_v186_enter_submit_and_appeals_starter_remain_wired() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "question.addEventListener('keydown'" in html
    assert "event.key === 'Enter' && !event.shiftKey" in html
    assert "event.preventDefault();" in html
    assert "ask();" in html
    assert 'data-example="What court handles appeals?"' in html
    assert '/api/runtime-diagnostics' in html
    assert "window.__MFL_WORKBENCH_UI_VERSION = '1.87.0-chat-library-routing-input-clear'" in html


def test_v186_runtime_diagnostics_version() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    payload = api.runtime_diagnostics()
    assert payload["version"] == "1.92.0"
    assert payload["ui_version"] == "1.87.0-chat-library-routing-input-clear"
    assert payload["enter_to_submit"] is True
    assert payload["appeals_routing_fix"] is True
    assert payload["brand_assets_mounted"] is True
