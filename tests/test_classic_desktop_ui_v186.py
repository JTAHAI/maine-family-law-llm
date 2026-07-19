from __future__ import annotations


def test_v186_workbench_matches_requested_classic_desktop_layout_markers() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html
    from maine_family_law_llm.version import UI_FOOTER_LABEL

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
    assert UI_FOOTER_LABEL in html


def test_v186_enter_submit_and_appeals_starter_remain_wired() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html
    from maine_family_law_llm.version import UI_VERSION

    html = render_local_workbench_html()
    assert "question.addEventListener('keydown'" in html
    assert "event.key === 'Enter' && !event.shiftKey" in html
    assert "event.preventDefault();" in html
    assert "ask();" in html
    assert 'data-example="What court handles appeals?"' in html
    assert '/api/runtime-diagnostics' in html
    assert f"window.__MFL_WORKBENCH_UI_VERSION = '{UI_VERSION}'" in html
    assert html.index('class="chat-scroll"') < html.index('class="composer" data-fixed-composer="true"')
    assert "html, body {" in html
    assert "overflow: hidden;" in html
    assert "chat-scroll {" in html
    assert "overflow: auto;" in html


def test_v186_runtime_diagnostics_version() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import __version__, api
    from maine_family_law_llm.version import UI_VERSION

    payload = api.runtime_diagnostics()
    assert payload["version"] == __version__
    assert payload["ui_version"] == UI_VERSION
    assert payload["enter_to_submit"] is True
    assert payload["appeals_routing_fix"] is True
    assert payload["brand_assets_mounted"] is True
    assert payload["constitutional_chat_shell_v208"] is True
