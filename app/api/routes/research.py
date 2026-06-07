from fastapi import APIRouter, Header

from app.services import ConversationAdapter
from app.api.security import review_response
from legal.verifiers.source_cards import SourceCardStore

router = APIRouter(tags=["research"])
adapter = ConversationAdapter()


def _source_card_from_payload(payload: dict) -> dict:
    cards = payload.get("source_cards") or []
    if cards:
        return cards[0]
    return {
        "source_id": "external-authority-store-required",
        "jurisdiction": "maine",
        "authority_status": "stale_unknown",
        "freshness_status": "unknown",
        "quote_span_available": False,
    }


@router.post("/query", summary="Ask a source-grounded Maine family-law question")
def query(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    source_card = _source_card_from_payload(payload)
    query_payload = {**payload, "source_cards": [source_card]}
    answer = adapter.for_query(query_payload, audience_hint=x_user_role)
    return review_response("POST /api/query", "source_grounded_query", answer)


@router.post("/research", summary="Retrieve relevant Maine authority")
def research(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    source_cards = payload.get("source_cards") or []
    source_card_store = SourceCardStore()
    for card in source_cards:
        source_card_store.add(card)
    response = adapter.for_research(
        {**payload, "source_cards": list(source_card_store.to_dict().values())},
        audience_hint=x_user_role,
    )
    return review_response("POST /api/research", "authority_research", response)
