from legal.conversation.workflow_steps import WorkflowStepPlanner


def test_workflow_steps_return_first_safe_prompt_and_missing_questions() -> None:
    planner = WorkflowStepPlanner()
    first = planner.first_step("check_citations")
    assert first["review_required"] is True
    assert "citation" in first["question"].lower()

    questions = planner.next_questions("check_citations", {})
    assert questions == ["Please provide citations."]
