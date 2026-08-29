from __future__ import annotations

import re


def _script_from(html: str) -> str:
    match = re.search(r"<script>(?P<script>.*)</script>", html, flags=re.S)
    assert match, "local workbench HTML must include one inline script block"
    return match.group("script")


def test_public_workbench_has_welcome_focus_help_and_context_controls() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    script = _script_from(html)

    assert 'id="welcome-button"' in html
    assert 'id="copy-link-button"' in html
    assert 'id="focus-mode-button"' in html
    assert 'id="help-button"' in html
    assert 'id="new-chat-button"' in html
    assert 'id="welcome-overlay"' in html
    assert 'id="help-overlay"' in html
    assert 'id="context-bar"' not in html
    assert 'class="context-chip"' not in html
    assert 'id="session-summary"' in html
    assert 'id="search-mode"' in html
    assert 'value="maine_law"' in html
    assert 'value="my_records"' in html
    assert '<option selected value="both">Both</option>' in html
    assert 'data-search-mode="both"' in html
    assert 'data-search-mode="both" role="radio" type="button">Both</button>' in html
    assert '<input checked id="child-impact-lens" type="checkbox"/>' in html
    assert 'Copy query link' in html
    assert 'Focus mode' in html
    assert 'Help &amp; tips' in html
    assert 'Choose how you want to begin' in html
    assert "syncContextBar" in script
    assert "openOverlay(welcomeOverlay)" in script
    assert "document.body.dataset.focusMode" in script
    assert "currentQuestionOrFallback" in script


def test_public_workbench_has_richer_answer_and_source_card_rendering() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    script = _script_from(html)

    assert "answer-callout" in html
    assert "section-nav" in html
    assert "source-card-badges" in html
    assert "source-snippet" in html
    assert "Open source link" in html
    assert "renderLatestAnswer" in script
    assert "renderParagraphBlocks" in script
    assert "Reviewer handoff copied." in script
    assert "Grounded answer ready." in script


def test_public_workbench_remains_public_and_case_agnostic() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()

    assert "TAHAI v MORSE" not in html
    assert "FAILED ADMINISTRATION of STATE OF MAINE" not in html
    assert "General Maine law workbench only" in html
