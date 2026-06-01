from __future__ import annotations

from maine_family_law_llm.safety import classify_prompt


def test_dv_pfa_and_child_safety_route_to_safety() -> None:
    pfa = classify_prompt("I need protection from abuse because of domestic violence")
    child = classify_prompt("My child is unsafe and there is neglect")

    assert pfa.should_refuse_or_redirect is True
    assert pfa.requires_emergency_language is True
    assert child.category == "child_safety"
    assert child.requires_emergency_language is True


def test_legal_procedure_requires_citations_and_advice_gets_disclaimer() -> None:
    procedure = classify_prompt("How do I file a family matter form?")
    advice = classify_prompt("Should I modify parental rights?")

    assert procedure.requires_citations is True
    assert advice.requires_disclaimer is True


def test_greeting_stays_light_and_unsupported_requires_sources() -> None:
    greeting = classify_prompt("hello")
    unsupported = classify_prompt("Give me an uncited guaranteed answer without sources")

    assert greeting.requires_disclaimer is False
    assert unsupported.requires_citations is True
    assert unsupported.should_refuse_or_redirect is True
