from __future__ import annotations


def test_expanded_chat_library_has_usability_depth() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_library

    items = get_chat_library()
    assert len(items) >= 25
    audiences = {item.audience for item in items}
    assert {"parent", "lawyer", "caregiver", "counselor", "therapist"}.issubset(audiences)
    topics = {item.topic for item in items}
    assert {"evidence_map", "jurisdiction", "professional_boundaries", "court_process"}.issubset(topics)
    payload = public_library()
    assert any("served" in " ".join(row["keywords"]) for row in payload)
    assert any(row["id"] == "therapist_records_caution" for row in payload)


def test_common_parent_and_professional_questions_are_grounded() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        "I was served with family court papers. What should I do first?",
        "How do I organize evidence for family court?",
        "Can my child choose which parent to live with?",
        "What jurisdiction issues should I flag in a Maine custody matter?",
        "Should I write a court letter for a parent?",
        "Can therapy records be used in family court?",
    ]
    for question in questions:
        payload = ask(AskRequest(question=question))
        answer = str(payload["answer"])
        assert payload["grounded"] is True, question
        assert payload["citations"], question
        assert "not legal advice" in answer.lower(), question


def test_ask_empty_question_returns_json_payload_not_server_error() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(AskRequest(question="   "))
    assert payload["grounded"] is False
    assert payload["failure_class"] == "empty_question"
    assert "Type a Maine family-law question" in str(payload["answer"])
    assert isinstance(payload["citations"], list)


def test_workbench_library_search_and_more_starters_are_present() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "id=\"library-search\"" in html
    assert "Served papers" in html
    assert "Organize evidence" in html
    assert "libraryItems" in html
    assert "renderQuestionLibrary(libraryItems)" in html
