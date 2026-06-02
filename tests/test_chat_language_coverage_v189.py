from __future__ import annotations


def test_v189_chat_library_expands_deadline_service_appeal_and_professional_coverage() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_prompt_packs, public_topics

    items = get_chat_library()
    assert len(items) >= 138
    topics = {row["topic"] for row in public_topics()}
    assert {"deadlines_service", "service", "records_access", "parentage", "appeal_preservation"}.issubset(topics)
    ids = {item.id for item in items}
    expected = {
        "parent_response_deadline_risk",
        "parent_service_problem_triage",
        "parent_out_of_state_service_triage",
        "parent_ecourts_record_access_boundary",
        "parent_parentage_first_questions",
        "lawyer_motion_for_findings_preservation",
        "lawyer_stay_pending_appeal_triage",
        "lawyer_interlocutory_nonfinal_appeal_triage",
        "counselor_hearing_support_boundary",
        "therapist_record_release_dispute_boundary",
    }
    assert expected.issubset(ids)
    packs = public_prompt_packs()
    assert any(pack["id"] == "appeals_service_deadline_triage" and pack["prompt_count"] >= 8 for pack in packs)


def test_v189_wrong_match_routes_more_real_world_phrasings() -> None:
    from maine_family_law_llm.chat_library import match_chat_library

    expected = {
        "How many days do I have to respond to divorce papers?": "parent_response_deadline_risk",
        "What if I cannot find the other parent to serve papers?": "parent_service_problem_triage",
        "How do I serve family papers if the other parent is out of state?": "parent_out_of_state_service_triage",
        "How do I ask to continue a hearing because I wasn't served correctly?": "parent_continue_service_defect_hearing",
        "What if eCourts says my family record is private or sealed?": "parent_ecourts_record_access_boundary",
        "What if I cannot afford the filing fee for a family case?": "parent_fee_waiver_forms_boundary",
        "Do I file parentage or divorce forms if we were never married?": "parent_parentage_first_questions",
        "What if child support arrears are piling up?": "parent_child_support_arrears_enforcement",
        "How should I prepare for a protection from abuse hearing?": "parent_pfa_hearing_prep_boundary",
        "How do I check final order, findings, and record issues before a family appeal?": "lawyer_appellate_finality_record_triage",
        "Should I file a motion for findings before appeal?": "lawyer_motion_for_findings_preservation",
        "Can I ask the court to stay a family order while I appeal?": "lawyer_stay_pending_appeal_triage",
        "Can I appeal a temporary order before final judgment?": "lawyer_interlocutory_nonfinal_appeal_triage",
        "How do I review a magistrate order in a family matter?": "lawyer_magistrate_order_objection_triage",
        "Can a counselor sit with me at the hearing and tell me what to say?": "counselor_hearing_support_boundary",
        "Can a therapist release records to one parent but not the other?": "therapist_record_release_dispute_boundary",
    }
    for question, item_id in expected.items():
        item = match_chat_library(question)
        assert item is not None, question
        assert item.id == item_id, question


def test_v189_new_questions_are_source_backed_review_required_and_not_legal_advice() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        "How many days do I have to respond to divorce papers?",
        "What if I cannot find the other parent to serve papers?",
        "What if eCourts says my family record is private or sealed?",
        "Can I appeal a temporary order before final judgment?",
        "Can a counselor sit with me at the hearing and tell me what to say?",
        "Can a therapist release records to one parent but not the other?",
    ]
    for question in questions:
        payload = ask(AskRequest(question=question, answer_style="checklist"))
        assert payload["grounded"] is True, question
        assert payload["review_required"] is True, question
        assert payload["citations"], question
        assert payload["failure_class"] == "none", question
        assert "not legal advice" in str(payload["answer"]).lower(), question


def test_v189_runtime_diagnostics_reports_language_and_plan_flags() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    payload = api.runtime_diagnostics()
    assert payload["version"] == "1.89.0"
    assert payload["chat_library_language_v189"] is True
    assert payload["enterprise_llm_chat_plan_v189"] == "docs/enterprise-llm-chat-ga-plan-v189.md"
