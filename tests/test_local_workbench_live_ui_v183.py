from __future__ import annotations

import re


def _script_from(html: str) -> str:
    match = re.search(r"<script>(?P<script>.*)</script>", html, flags=re.S)
    assert match, "local workbench HTML must include one inline script block"
    return match.group("script")


def test_live_ui_has_unambiguous_branding_and_enter_submit_marker() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    script = _script_from(html)

    assert 'id="focaf-brand-shell"' in html
    assert 'data-ui-version="1.86.0-classic-desktop-focaf-workbench"' in html
    assert "focaf.jtforme.com" in html
    assert "UI v1.86 classic desktop FOCAF research workbench + Enter submit + appeals/runtime diagnostics" in html
    assert "window.__MFL_WORKBENCH_UI_VERSION = '1.86.0-classic-desktop-focaf-workbench'" in script
    assert "question.addEventListener('keydown'" in script
    assert "event.key === 'Enter' && !event.shiftKey" in script
    assert "event.preventDefault();" in script
    assert "ask();" in script


def test_v183_local_workbench_script_does_not_break_on_transcript_newline_literals() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    script = _script_from(render_local_workbench_html())

    # Regression for v1.82: Python string interpolation emitted real newlines inside
    # JavaScript single-quoted string literals around join('\n'), which made the whole
    # browser script fail before Enter handlers or prompt-pack loading could attach.
    assert "join('\n" not in script
    assert "].join('\n" not in script
    assert "join('\\n\\n')" in script
    assert "].join('\\n')" in script
    assert "`[${msg.at}] ${msg.role.toUpperCase()}\\n${msg.text}`" in script
