from __future__ import annotations


def test_v181_library_adds_prompt_packs_and_more_everyday_questions() -> None:
    from maine_family_law_llm.chat_library import get_chat_library, public_prompt_packs, public_topics

    items = get_chat_library()
    assert len(items) >= 78
    ids = {item.id for item in items}
    assert {
        "parent_ask_lawyer_before_filing",
        "parent_court_clerk_questions",
        "parent_fee_waiver_filing_costs",
        "parent_service_of_process_basics",
        "parent_agreement_parenting_plan",
        "parent_pfa_served_response",
        "lawyer_opposition_review_checklist",
        "lawyer_appeal_preservation_triage",
        "caregiver_guardianship_vs_parental_rights",
        "counselor_client_asks_what_to_file",
        "counselor_testimony_request_boundary",
        "therapist_child_resists_contact",
        "public_download_share_test",
    }.issubset(ids)

    packs = public_prompt_packs()
    assert len(packs) >= 6
    assert {pack["audience"] for pack in packs} >= {"parent", "lawyer", "caregiver", "counselor", "therapist"}
    assert all(pack["prompt_count"] >= 5 for pack in packs)
    assert any(prompt["recommended_style"] == "questions_to_ask" for pack in packs for prompt in pack["prompts"])

    topics = {row["topic"] for row in public_topics()}
    assert {"questions_to_ask", "draft_review", "local_workbench_use"}.issubset(topics)


def test_v181_new_questions_are_grounded_and_review_required() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    questions = [
        ("What should I ask a lawyer before filing a family case?", "questions_to_ask"),
        ("What can I ask the court clerk about my family case?", "questions_to_ask"),
        ("What if I cannot afford family court filing fees?", "checklist"),
        ("How do I serve family court papers in Maine?", "checklist"),
        ("What if we agree on a parenting plan?", "checklist"),
        ("What if the other parent has substance use issues?", "checklist"),
        ("What should I know if a GAL is involved?", "checklist"),
        ("How should I organize school and medical records for family court?", "checklist"),
        ("I was served with protection from abuse papers. What should I do first?", "checklist"),
        ("Give me a checklist for opposing a Maine family motion.", "checklist"),
        ("How should I review a parenting settlement before filing?", "source_card_table"),
        ("What should I check for appeal preservation in a family case?", "checklist"),
        ("A client asked me what to file in family court. What can I say?", "professional_boundary"),
        ("A parent wants me to testify in family court. What should I consider?", "professional_boundary"),
        ("A child resists contact with a parent. What should a therapist do?", "professional_boundary"),
    ]
    for question, style in questions:
        payload = ask(AskRequest(question=question, answer_style=style))
        assert payload["grounded"] is True, question
        assert payload["citations"], question
        assert payload["review_required"] is True, question
        assert payload["source_card_count"] == len(payload["citations"]), question
        assert payload["metadata"].get("matched_library_id"), question
        assert "not legal advice" in str(payload["answer"]).lower(), question


def test_v181_questions_to_ask_style_separates_lawyer_and_clerk_questions() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(
        AskRequest(
            question="What can I ask the court clerk about my family case?",
            answer_style="questions_to_ask",
        )
    )
    answer = str(payload["answer"])
    assert "Questions to ask next" in answer
    assert "Ask a lawyer / qualified reviewer" in answer
    assert "Ask a court clerk only about logistics" in answer
    assert "Clerks cannot choose claims" in answer


def test_v181_ui_has_role_prompt_packs_source_inspector_and_json_export() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert 'id="prompt-pack-select"' in html
    assert 'id="prompt-pack-list"' in html
    assert "/api/starter-prompt-packs" in html
    assert "loadPromptPacks" in html
    assert "renderPromptPacks" in html
    assert "data-pack-prompt" in html
    assert "questions_to_ask" in html
    assert 'id="download-json-button"' in html
    assert "local_chat_transcript_v3" in html
    assert 'id="source-inspector"' in html
    assert "data-inspect-source" in html
    assert "inspectSource" in html


def test_v181_starter_prompt_packs_endpoint_available() -> None:
    pytest = __import__("pytest")
    pytest.importorskip("fastapi")
    from maine_family_law_llm.api import starter_prompt_packs

    payload = starter_prompt_packs()
    assert isinstance(payload, list)
    assert any(pack["id"] == "parent_first_30_minutes" for pack in payload)
    assert any(pack["audience"] == "therapist" for pack in payload)
    assert all("prompts" in pack for pack in payload)
