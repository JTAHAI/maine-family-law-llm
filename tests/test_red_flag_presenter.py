from legal.conversation.red_flag_presenter import RedFlagPresenter


def test_red_flag_presenter_is_prominent_but_calm() -> None:
    payload = RedFlagPresenter().present(["Emergency or safety risk detected. Use official emergency or safety help first."])
    assert payload["has_red_flags"] is True
    assert "attention" in payload["summary"]
