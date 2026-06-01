from __future__ import annotations


def test_v180_library_expands_everyday_questions_and_topics() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_topics

    items = get_chat_library()
    assert len(items) >= 54
    ids = {item.id for item in items}
    assert {
        "parent_divorce_first_steps",
        "parent_temporary_order_prep",
        "parent_communication_messages",
        "lawyer_intake_triage_parental_rights",
        "caregiver_grandparent_contact_question",
        "counselor_subpoena_or_order",
        "therapist_no_private_uploads",
        "therapist_safety_contact_boundary",
    }.issubset(ids)
    topics = {row["topic"] for row in public_topics()}
    assert {"divorce", "intake_triage", "appeal_preservation", "authority_matrix"}.issubset(topics)


def test_v180_new_everyday_questions_are_source_grounded() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        "What should I do first in a Maine divorce?",
        "We were never married. How do parental rights work in Maine?",
        "How do I prepare for a temporary order hearing?",
        "Can I ask for supervised visits?",
        "How should I organize texts and app messages for court?",
        "My income changed. What should I gather for child support?",
        "Give me an intake checklist for a Maine parental rights case.",
        "What should a counselor do if subpoenaed in a family case?",
        "Can I paste session notes into this workbench?",
        "A child told me where they want to live. What should a therapist do?",
    ]
    for question in questions:
        payload = ask(AskRequest(question=question, answer_style="checklist"))
        assert payload["grounded"] is True, question
        assert payload["citations"], question
        assert payload["review_required"] is True, question
        assert payload["source_card_count"] == len(payload["citations"]), question
        assert payload["metadata"].get("matched_library_id"), question
        assert "not legal advice" in str(payload["answer"]).lower(), question


def test_v180_new_answer_styles_are_available_and_useful() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    intake = ask(AskRequest(question="Give me an intake checklist for a Maine parental rights case.", answer_style="intake"))
    assert "Intake triage" in str(intake["answer"])
    assert "Intake questions to ask next" in str(intake["answer"])

    boundary = ask(AskRequest(question="Can I paste session notes into this workbench?", answer_style="professional_boundary"))
    assert "Professional-boundary note" in str(boundary["answer"])
    assert "Boundary guardrails" in str(boundary["answer"])

    source_table = ask(AskRequest(question="How do I audit source cards before using an answer?", answer_style="source_card_table"))
    assert "Source-card audit table" in str(source_table["answer"])
    assert "| Source | Type | Citation hint | Why it matters |" in str(source_table["answer"])


def test_v180_ui_has_topic_filter_richer_exports_and_source_copy() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert 'id="topic-filter"' in html
    assert 'id="library-topic-search"' in html
    assert "populateTopicFilter" in html
    assert "Latest payload metadata:" in html
    assert "Latest source cards:" in html
    assert "data-copy-source" in html
    assert "source_card_table" in html
    assert "/api/question-topics" in html


def test_v180_question_topics_endpoint_available() -> None:
    pytest = __import__("pytest")
    pytest.importorskip("fastapi")
    from maine_family_law_llm.api import question_topics

    payload = question_topics()
    assert isinstance(payload, list)
    assert any(row["topic"] == "professional_boundaries" for row in payload)
    assert any("therapist" in row["audiences"] for row in payload)
