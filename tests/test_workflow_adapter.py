from app.services.workflow_adapter import WorkflowAdapter


def test_workflow_adapter_returns_start_menu_and_route_first_step() -> None:
    adapter = WorkflowAdapter()
    menu = adapter.start(audience="self_represented")
    assert menu["review_required"] is True
    assert any(row["workflow_id"] == "self_represented_start_here" for row in menu["workflows"])

    route = adapter.route("I need to review a protection from abuse overlap.", audience="advocate")
    assert route["workflow_id"] == "protection_from_abuse_overlap_review"
    assert route["first_step"]["review_required"] is True


def test_workflow_adapter_next_questions_are_review_required() -> None:
    payload = WorkflowAdapter().next_questions("draft_or_review_a_motion", {})
    assert payload["review_required"] is True
    assert payload["questions"]
