from __future__ import annotations

import inspect

from corpus_builder_support import build_fixture_case
from maine_family_law_llm import api
from maine_family_law_llm.case_library import active_case_root, list_registered_case_roots, register_case_root, set_active_case_root
from maine_family_law_llm.local_workbench_ui import render_local_workbench_html


def test_case_library_registers_multiple_case_roots_and_tracks_active_case(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "case_library.json"
    monkeypatch.setenv("MFL_CASE_LIBRARY_PATH", str(registry_path))
    built_one = build_fixture_case(tmp_path / "matter_one", case_name="Matter One")
    built_two = build_fixture_case(tmp_path / "matter_two", case_name="Matter Two")

    register_case_root(built_one["case_root"])
    set_active_case_root(built_two["case_root"])

    registered = list_registered_case_roots()
    assert len(registered) == 2
    assert registered[0]["active"] is True
    assert registered[0]["label"] == "Matter Two"
    assert active_case_root() == built_two["case_root"].resolve()


def test_api_ask_uses_active_case_corpus_when_one_is_selected(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "case_library.json"
    monkeypatch.setenv("MFL_CASE_LIBRARY_PATH", str(registry_path))
    built = build_fixture_case(tmp_path / "matter_api", case_name="Matter API")
    set_active_case_root(built["case_root"])

    payload = api.ask(api.AskRequest(question="What does the corpus show about school attendance and records access?"))

    assert payload["corpus_mode"] == "active_case_corpus"
    assert payload["active_case_label"] == "Matter API"
    assert payload["active_case_root"] == str(built["case_root"].resolve())
    assert payload["citations"]
    assert payload["source_card_count"] >= 1


def test_browser_workbench_exposes_corpus_library_switcher() -> None:
    html = render_local_workbench_html()
    assert "Corpus library" in html
    assert "Use selected corpus" in html
    assert "/api/corpus-library" in html
    assert "/api/activate-corpus" in html
    assert "General Maine law workbench only" in html


def test_launcher_source_mentions_installed_corpus_library_controls() -> None:
    from app import launcher

    build_ui_source = inspect.getsource(launcher.MaineFamilyLawLauncher._build_ui)
    assert "Installed corpus library" in build_ui_source
    assert "Use selected corpus" in build_ui_source
    assert "Switch the active corpus here" in build_ui_source
