from __future__ import annotations

from maine_family_law_llm.answer import compose_answer
from maine_family_law_llm.draft import draft_from_sources
from maine_family_law_llm.safety import classify_prompt
from maine_family_law_llm.workbench import retrieve_fixture_sources


def test_legal_answer_includes_citations_and_effective_warning() -> None:
    question = "How do I start a family matter?"
    retrieval = retrieve_fixture_sources(question)
    answer = compose_answer(question, retrieval.results, classify_prompt(question))

    assert answer.grounded is True
    assert "Citation appendix:" in answer.answer
    assert "legal advice" in answer.answer
    assert "effective date" in answer.answer.lower()


def test_no_source_legal_answer_refuses_substantive_claim() -> None:
    question = "How do I file this obscure unsupported thing?"
    answer = compose_answer(question, [], classify_prompt(question))

    assert answer.grounded is False
    assert answer.failure_class == "sources_missing_for_legal_answer"
    assert "no supporting Maine source" in answer.answer


def test_general_greeting_remains_normal() -> None:
    answer = compose_answer("hello", [], classify_prompt("hello"))

    assert answer.grounded is False
    assert answer.failure_class == "general_information_not_source_backed"
    assert "attorney-client" not in answer.answer.lower()


def test_general_substantive_question_keeps_retrieved_sources() -> None:
    question = "What records should I preserve before a hearing?"
    retrieval = retrieve_fixture_sources(question)

    answer = compose_answer(question, retrieval.results, classify_prompt(question))

    assert answer.grounded is True
    assert answer.citations
    assert "Based on the retrieved source snippets:" in answer.answer


def test_draft_helper_warns_not_filing_ready_and_uses_citations() -> None:
    retrieval = retrieve_fixture_sources("child support form checklist")
    draft = draft_from_sources("child support form checklist", retrieval.results, mode="checklist")

    assert draft.failure_class == "none"
    assert "not filing-ready" in draft.text
    assert "Citation appendix:" in draft.text
    assert "FM-999" not in draft.text


def test_draft_refuses_missing_sources() -> None:
    draft = draft_from_sources("draft unsupported filing", [], mode="court_form_prep_notes")

    assert draft.failure_class == "sources_missing_for_draft"
    assert "without retrieved Maine sources" in draft.text
