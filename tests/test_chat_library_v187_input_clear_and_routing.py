from __future__ import annotations


def test_v187_enter_submit_clears_question_box_after_accepting_input() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "event.key === 'Enter' && !event.shiftKey" in html
    assert "const text = question.value.trim();" in html
    assert "addMessage('user', text);" in html
    assert "question.value = '';" in html
    assert "question.dataset.lastSubmitCleared = 'true';" in html
    assert "enter_submit_clears_input" in html


def test_v187_runtime_diagnostics_reports_input_clear_and_routing_flags() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    payload = api.runtime_diagnostics()
    assert payload["version"] == "2.05.0"
    assert payload["ui_version"] == "1.87.0-chat-library-routing-input-clear"
    assert payload["enter_to_submit"] is True
    assert payload["enter_submit_clears_input"] is True
    assert payload["chat_library_routing_v187"] is True


def test_v187_wrong_match_routes_common_questions_to_correct_library_items() -> None:
    from maine_family_law_llm.chat_library import match_chat_library

    expected = {
        "Which court do I file a family case in?": "parent_family_court_routing",
        "What court handles appeals?": "parent_appeals_court_routing",
        "What is a GAL and their role?": "parent_gal_role_report_questions",
        "Can I serve papers by mail?": "parent_service_method_check",
        "What if the other parent never answered?": "parent_default_or_no_response",
        "How is child support calculated?": "parent_support_calculation_boundary",
        "Can a protection from abuse order affect parenting time?": "parent_pfa_children_contact_overlap",
        "What UCCJEA facts should I gather first?": "lawyer_uccjea_home_state_triage",
    }
    for question, item_id in expected.items():
        item = match_chat_library(question)
        assert item is not None, question
        assert item.id == item_id, question


def test_v187_new_real_world_questions_are_source_backed_and_review_required() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        "Which court do I file a family case in?",
        "Can I serve papers by mail?",
        "What if the other parent never answered?",
        "What if DHHS is involved in my family case?",
        "Can a reunification therapist write a progress report for court?",
    ]
    for question in questions:
        payload = ask(AskRequest(question=question))
        assert payload["grounded"] is True, question
        assert payload["review_required"] is True, question
        assert payload["citations"], question
        assert "not legal advice" in str(payload["answer"]).lower(), question
