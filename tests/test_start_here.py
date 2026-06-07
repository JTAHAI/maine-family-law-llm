from legal.conversation.start_here import StartHereBuilder


def test_start_here_menu_defaults_to_review_required_and_includes_workflows() -> None:
    menu = StartHereBuilder().menu(audience="self_represented")
    workflow_ids = {row["workflow_id"] for row in menu["workflows"]}
    assert menu["review_required"] is True
    assert menu["filing_ready_status"] == "blocked_from_filing_ready"
    assert "self_represented_start_here" in workflow_ids
