from legal.conversation.workflow_router import WorkflowRouter


def test_workflow_router_infers_attorney_motion_workflow() -> None:
    route = WorkflowRouter().infer("Draft a motion to modify after changed circumstances.", audience="attorney")
    assert route.workflow_id == "draft_or_review_a_motion"
    assert route.confidence > 0.5


def test_workflow_router_asks_clarifying_question_for_ambiguous_unknown_request() -> None:
    route = WorkflowRouter().infer("Help.", audience="unknown")
    assert route.ambiguous is True
    assert route.clarification_question
