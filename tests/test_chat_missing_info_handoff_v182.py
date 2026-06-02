from __future__ import annotations


def test_v182_library_adds_missing_info_and_handoff_coverage() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_missing_information_prompts, public_prompt_packs, public_topics

    items = get_chat_library()
    assert len(items) >= 104
    ids = {item.id for item in items}
    assert {
        "parent_case_management_conference_prep",
        "parent_mediation_prep",
        "parent_missing_documents_before_asking",
        "parent_order_language_confusing",
        "parent_cannot_follow_order_this_weekend",
        "parent_child_support_arrears_or_missed_payment",
        "lawyer_missing_info_intake_builder",
        "lawyer_reviewer_handoff_from_chat",
        "lawyer_proposed_findings_source_map",
        "lawyer_deadline_service_audit",
        "lawyer_client_document_request_pack",
        "caregiver_parent_returns_or_objects",
        "caregiver_school_enrollment_authority",
        "caregiver_private_records_boundary",
        "caregiver_lawyer_questions_pack",
        "counselor_parent_wants_strategy",
        "counselor_records_release_to_lawyer",
        "counselor_treatment_summary_request",
        "therapist_unclear_court_order",
        "therapist_parent_requests_opinion_letter",
        "therapist_records_subpoena_handoff",
        "public_reviewer_handoff_export",
    }.issubset(ids)

    topics = {row["topic"] for row in public_topics()}
    assert {"missing_information", "order_review", "local_workbench_use"}.issubset(topics)

    missing = public_missing_information_prompts()
    assert len(missing) == len(items)
    assert all(row["missing_information"] for row in missing)
    assert all(row["follow_up_questions"] for row in missing)
    assert any(row["item_id"] == "lawyer_reviewer_handoff_from_chat" for row in missing)

    packs = public_prompt_packs()
    assert len(packs) >= 7
    assert any(pack["id"] == "reviewer_handoff_missing_info" for pack in packs)
    assert any(prompt["recommended_style"] == "missing_information" for pack in packs for prompt in pack["prompts"])


def test_v182_missing_information_style_returns_reviewer_handoff_metadata() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        "What information do I need before asking a family law question?",
        "How do I prepare for a case management conference in family court?",
        "How should I prepare for mediation in a Maine parenting case?",
        "I don't understand my parenting order. What should I check?",
        "What if I cannot follow the parenting order this weekend?",
        "What should I do if child support payments were missed?",
        "Build a missing information list for a new family case intake.",
        "How should I review a transcript from the local workbench?",
        "What documents should I ask a family-law client to send first?",
        "What should a caregiver ask a lawyer before filing anything?",
        "Can I enroll a child in school as a caregiver?",
        "Can I upload a child's school or medical records to this tool?",
        "A client wants legal strategy for family court. What can a counselor do?",
        "Can I write a treatment summary for family court?",
        "What if a court order about therapy is unclear?",
        "A parent asked me for a custody opinion letter. What should I do?",
        "How do I export a reviewer handoff from this chat?",
    ]
    for question in questions:
        payload = ask(AskRequest(question=question, answer_style="missing_information"))
        answer = str(payload["answer"])
        assert payload["grounded"] is True, question
        assert payload["citations"], question
        assert payload["review_required"] is True, question
        assert "Missing-information checklist" in answer, question
        assert "Role-specific follow-up questions" in answer, question
        assert "not legal advice" in answer.lower(), question
        metadata = payload["metadata"]
        assert metadata.get("matched_library_id"), question
        assert metadata.get("missing_information"), question
        assert metadata.get("follow_up_questions"), question
        assert metadata.get("reviewer_handoff_ready") is True, question


def test_v182_api_exposes_missing_information_endpoint() -> None:
    pytest = __import__("pytest")
    pytest.importorskip("fastapi")
    from maine_family_law_llm.api import api_version, missing_information_prompts

    assert api_version()["version"] >= "1.82.0"
    payload = missing_information_prompts()
    assert isinstance(payload, list)
    assert any(row["item_id"] == "parent_missing_documents_before_asking" for row in payload)
    assert all("follow_up_questions" in row for row in payload)


def test_v182_ui_has_missing_info_handoff_and_export_metadata() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert 'value="missing_information"' in html
    assert 'id="handoff-panel"' in html
    assert "renderHandoff" in html
    assert "reviewer_handoff" in html
    assert "Copy reviewer handoff JSON" in html
    assert "local_chat_transcript_v3" in html
    assert "/api/missing-information-prompts" in html
