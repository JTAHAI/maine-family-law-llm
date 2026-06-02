from __future__ import annotations


def test_v184_appeals_question_routes_to_appeals_answer_not_parenting_schedule() -> None:
    from maine_family_law_llm.answer import compose_answer
    from maine_family_law_llm.chat_library import expand_query_for_library
    from maine_family_law_llm.safety import classify_prompt
    from maine_family_law_llm.workbench import retrieve_fixture_sources

    question = "What court handles appeals?"
    retrieval = retrieve_fixture_sources(expand_query_for_library(question), limit=6)
    answer = compose_answer(question, retrieval.results, classify_prompt(question), answer_style="plain_language")

    assert answer.grounded is True
    assert answer.metadata["matched_library_id"] == "parent_appeals_court_routing"
    assert "Supreme Judicial Court" in answer.answer
    assert "Law Court" in answer.answer
    assert "parenting/contact schedule" not in answer.answer
    assert "weekly schedule" not in answer.answer


def test_v184_runtime_diagnostics_endpoint_and_html_markers() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    diagnostics = api.runtime_diagnostics()
    assert diagnostics["version"] == "1.89.0"
    assert diagnostics["ui_version"] == "1.87.0-chat-library-routing-input-clear"
    assert diagnostics["enter_to_submit"] is True
    assert diagnostics["appeals_routing_fix"] is True

    html = render_local_workbench_html()
    assert 'data-ui-version="1.87.0-chat-library-routing-input-clear"' in html
    assert 'id="runtime-diagnostics"' in html
    assert "What court handles appeals?" in html
    assert "/api/runtime-diagnostics" in html
    assert "focaf.jtforme.com" in html
