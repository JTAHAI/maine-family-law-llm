from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_local_workbench_html_has_real_chat_controls() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "Maine Family Law LLM" in html
    assert "id=\"question\"" in html
    assert "id=\"ask-button\"" in html
    assert "/ui-assets/workbench.js" in html
    script = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert "fetch('/ask/stream'" in script
    assert "fetchAnswerStream" in script
    assert "Retrieved source cards" in html
    assert "data-source-card" in html
    assert "Not legal advice" in html or "not legal advice" in html


def test_local_api_exposes_browser_workbench_and_chat_aliases() -> None:
    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    assert api.app is not None
    html = api.local_chat_workbench()
    assert "Local source-backed chat workbench" in html
    assert api.workbench() == html

    payload = api.api_chat(api.AskRequest(question="What Maine sources should I check for child support?"))
    assert payload["citations"]
    assert payload["grounded"] is True

    version = api.api_version()
    assert version["workbench_url"] == "/"


def test_nontechnical_start_scripts_and_readme_are_present() -> None:
    assert (ROOT / "START_LOCAL_CHAT.ps1").is_file()
    assert (ROOT / "START_LOCAL_CHAT.cmd").is_file()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "For non-technical local testing" in readme
    assert ".\\START_LOCAL_CHAT.ps1" in readme
    assert "http://127.0.0.1:8000/" in readme
    assert "Download" in readme
