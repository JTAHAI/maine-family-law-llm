from __future__ import annotations


V190_EXPECTED_ROUTES = {
    "What can I ask the court clerk in my family case?": "parent_clerk_vs_lawyer_boundary",
    "How do I ask for an interpreter or ADA accommodation in family court?": "parent_interpreter_ada_accommodation_forms",
    "I got a new order after court. What should I check first?": "parent_after_hearing_order_next_steps",
    "Can I file an emergency motion in a Maine parenting case?": "parent_emergency_motion_boundary",
    "What if a PFA order was violated?": "parent_pfa_violation_enforcement_boundary",
    "Is child support handled by DHHS or the court?": "parent_support_dhhs_vs_court_order",
    "What financial affidavit or income paperwork should I gather?": "parent_financial_affidavit_disclosure_prep",
    "Do I need a transcript for a family appeal?": "parent_appeal_transcript_record_check",
    "Is this a motion to reconsider or relief from judgment issue?": "lawyer_rule_60_reconsideration_relief_triage",
    "Build a contempt evidence checklist for a Maine family order.": "lawyer_contempt_evidence_burden_checklist",
    "What proof do I need to handle school or medical issues for a child I care for?": "caregiver_school_medical_authority_proof",
    "What if I disagree with GAL fees or the GAL report?": "parent_gal_fees_scope_objection_triage",
    "What should a counselor do after receiving a subpoena for family court?": "counselor_subpoena_records_triage",
    "Can a therapist do a custody evaluation if the court order asks?": "therapist_court_ordered_evaluation_boundary",
}


def test_v190_library_is_broader_and_has_unique_ids() -> None:
    from collections import Counter

    from maine_family_law_llm.chat_library import get_chat_library, public_prompt_packs, public_topics

    items = get_chat_library()
    assert len(items) >= 152
    ids = [item.id for item in items]
    assert [item_id for item_id, count in Counter(ids).items() if count > 1] == []
    assert set(V190_EXPECTED_ROUTES.values()).issubset(set(ids))

    topic_counts = {row["topic"]: row["count"] for row in public_topics()}
    assert topic_counts["questions_to_ask"] >= 5
    assert topic_counts["child_support"] >= 7
    assert topic_counts["appeal_preservation"] >= 10
    assert topic_counts["professional_boundaries"] >= 27

    packs = public_prompt_packs()
    assert any(pack["id"] == "v190_operator_and_review_triage" and pack["prompt_count"] >= 10 for pack in packs)


def test_v190_wrong_match_routes_real_world_phrasing() -> None:
    from maine_family_law_llm.chat_library import match_chat_library

    for question, item_id in V190_EXPECTED_ROUTES.items():
        item = match_chat_library(question)
        assert item is not None, question
        assert item.id == item_id, question


def test_v190_new_questions_are_grounded_review_required_and_safe() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    for question in V190_EXPECTED_ROUTES:
        payload = ask(AskRequest(question=question, answer_style="checklist"))
        assert payload["grounded"] is True, question
        assert payload["review_required"] is True, question
        assert payload["citations"], question
        assert payload["failure_class"] == "none", question
        answer = str(payload["answer"]).lower()
        assert "not legal advice" in answer, question
        assert "filing-ready" in answer or "filing ready" in answer, question


def test_v190_runtime_diagnostics_reports_command_compatibility() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    payload = api.runtime_diagnostics()
    assert payload["version"] == "1.90.0"
    assert payload["chat_library_language_v190"] is True
    assert payload["operator_command_compatibility_v190"] is True
    assert payload["chat_language_v190_report"] == "docs/chat-language-coverage-local-commands-pass-v190.md"
