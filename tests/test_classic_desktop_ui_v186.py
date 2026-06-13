from __future__ import annotations


def test_v186_workbench_matches_requested_classic_desktop_layout_markers() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "WE THE PEOPLE" in html
    assert "... establish JUSTICE ..." in html
    assert "Maine Family Law LLM" in html
    assert 'class="app-shell"' in html
    assert 'class="hero-banner"' in html
    assert 'class="main-stage"' in html
    assert 'data-chat-layout="primary"' in html
    assert 'class="right-rail"' in html
    assert 'Prompt shortcuts' in html
    assert 'Prompt packs' in html
    assert 'Source cards' in html
    assert 'Latest answer' in html
    assert 'Reviewer handoff' in html
    assert 'UI v2.08 modern constitutional chat workbench' in html


def test_v186_enter_submit_and_appeals_starter_remain_wired() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "question.addEventListener('keydown'" in html
    assert "event.key === 'Enter' && !event.shiftKey" in html
    assert "event.preventDefault();" in html
    assert "ask();" in html
    assert 'data-example="What court handles appeals?"' in html
    assert '/api/runtime-diagnostics' in html
    assert "window.__MFL_WORKBENCH_UI_VERSION = '2.08.0-modern-constitutional-chat'" in html
    assert html.index('class="chat-scroll"') < html.index('class="composer" data-fixed-composer="true"')
    assert "html, body {" in html
    assert "overflow: hidden;" in html
    assert "chat-scroll {" in html
    assert "overflow: auto;" in html


def test_v186_runtime_diagnostics_version() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import __version__, api

    payload = api.runtime_diagnostics()
    assert payload["version"] == __version__
    assert payload["ui_version"] == "2.08.0-modern-constitutional-chat"
    assert payload["enter_to_submit"] is True
    assert payload["appeals_routing_fix"] is True
    assert payload["brand_assets_mounted"] is True
    assert payload["constitutional_chat_shell_v208"] is True
