from __future__ import annotations


def test_question_library_has_core_audiences_and_prompts() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_library

    items = get_chat_library()
    audiences = {item.audience for item in items}
    assert {"parent", "lawyer", "caregiver", "counselor", "therapist"}.issubset(audiences)
    assert any("therapist" in item.keywords for item in items)
    assert any("child support" in item.keywords for item in items)
    assert len(public_library()) >= 10


def test_therapist_contact_question_gets_source_backed_answer() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(AskRequest(question="Can a therapist decide whether visits happen?"))

    answer = str(payload["answer"])
    assert payload["grounded"] is True
    assert "therapist" in answer.lower()
    assert "court authority" in answer.lower() or "parenting contact decisions" in answer.lower()
    assert payload["citations"]


def test_child_support_question_gets_preparation_answer() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(AskRequest(question="What should I gather for child support?", answer_style="checklist"))
    answer = str(payload["answer"])

    assert payload["grounded"] is True
    assert "Child Support Affidavit" in answer or "child-support" in answer
    assert "[ ]" in answer
    assert payload["citations"]


def test_workbench_has_error_json_handling_enter_submit_and_branding() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "WE THE PEOPLE" in html
    assert "... establish JUSTICE ..." in html
    assert "id=\"audience\"" in html
    assert "id=\"transcript\"" in html
    assert "fetchJson" in html
    assert "non-JSON response" in html
    assert "event.key === 'Enter' && !event.shiftKey" in html
    assert "/api/question-library" in html
    assert "Download transcript" in html


def test_question_library_endpoint_available() -> None:
    pytest = __import__("pytest")
    pytest.importorskip("fastapi")
    from maine_family_law_llm.api import question_library

    payload = question_library()
    assert isinstance(payload, list)
    assert any(item["audience"] == "parent" for item in payload)
    assert any(item["audience"] == "therapist" for item in payload)
