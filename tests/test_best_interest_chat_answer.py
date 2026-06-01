from __future__ import annotations


def test_best_interest_question_returns_factor_list() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(AskRequest(question="What are Maine's best-interest factors under 19-A M.R.S. § 1653?"))

    assert payload["grounded"] is True
    answer = str(payload["answer"])
    assert "19-A M.R.S. § 1653(3)" in answer
    assert "A. The age of the child." in answer
    assert "S. Whether allocation of some or all parental rights" in answer
    assert "Citation appendix:" in answer
    assert payload["citations"]


def test_best_interest_checklist_style_has_checkboxes() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(
        AskRequest(
            question="best interest factors for parental rights",
            answer_style="checklist",
            matter_context="parental rights and responsibilities",
        )
    )

    answer = str(payload["answer"])
    assert "Checklist: Maine best-interest factors" in answer
    assert "[ ] A. The age of the child." in answer
    assert payload["answer_style"] == "checklist"
    assert payload["matter_context_used"] is True


def test_workbench_has_input_and_output_controls() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html

    html = render_local_workbench_html()
    assert "id=\"answer-style\"" in html
    assert "id=\"matter-context\"" in html
    assert "id=\"copy-button\"" in html
    assert "id=\"answer-badges\"" in html
    assert "Best-interest factors" in html
    assert "renderBadges" in html
