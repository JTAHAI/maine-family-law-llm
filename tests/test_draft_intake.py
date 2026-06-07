from legal.conversation.draft_intake import DraftIntakeAnalyzer


def test_draft_intake_identifies_missing_required_fields() -> None:
    result = DraftIntakeAnalyzer().analyze("motion_to_modify", {"requested_relief": "modify contact"})
    assert result["supported"] is True
    assert "existing_orders" in result["missing_required_fields"]
    assert "changed_circumstances" in result["missing_required_fields"]
