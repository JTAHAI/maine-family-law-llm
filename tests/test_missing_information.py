from legal.conversation import MissingInformationEngine


def test_missing_information_engine_flags_missing_required_fields() -> None:
    engine = MissingInformationEngine()
    items = engine.analyze(
        workflow="motion_to_modify",
        payload={"changed_circumstances": "child moved schools"},
        audience="attorney",
        text="Need to modify the order.",
    )
    fields = {item.field for item in items}
    assert "existing_orders" in fields
    assert "requested_relief" in fields


def test_missing_information_engine_detects_deadline_and_confidentiality_risks() -> None:
    engine = MissingInformationEngine()
    items = engine.analyze(
        workflow="document_review",
        payload={"requested_relief": "review"},
        audience="self_represented",
        text="The hearing is tomorrow and the records are sealed.",
    )
    severities = {item.severity for item in items}
    assert "red_flag" in severities
    assert "warning" in severities
