from legal.conversation import SourceCardPresenter


def test_source_card_presenter_normalizes_verified_status() -> None:
    presenter = SourceCardPresenter()
    cards = presenter.present(
        [
            {
                "source_id": "source-1",
                "title": "Title 19-A",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh_verified",
                "jurisdiction": "maine",
            }
        ]
    )
    assert cards[0]["source_scope_status"] == "source_verified"
    assert cards[0]["status_label"] == "Source verified"


def test_source_card_presenter_marks_stale_unknown_cards_as_not_supporting_current_law() -> None:
    presenter = SourceCardPresenter()
    cards = presenter.present([{"source_id": "source-1", "freshness_status": "unknown"}])
    assert cards[0]["can_support_current_law_claim"] is False
