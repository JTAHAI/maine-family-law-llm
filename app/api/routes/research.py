from fastapi import APIRouter

from app.api.security import review_response
from legal.verifiers.source_cards import SourceCardStore

router = APIRouter(tags=["research"])


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
def query(payload: dict):
    source_card = _source_card_from_payload(payload)
    answer = {
        "status": "review_required",
        "query": payload.get("query"),
        "answer": None,
        "claims": [],
        "source_cards": [source_card],
        "drilldown": {
            "answer_to_claim_to_citation_to_source_text_to_verifier_result": True,
            "claim": None,
            "citation": source_card.get("citation"),
            "source_text": None,
            "verifier_result": "external_authority_store_required_before_authoritative_answer",
        },
        "message": "Authoritative answers require live official authority ingestion and verifier evidence.",
    }
    return review_response("POST /api/query", "source_grounded_query", answer)


@router.post("/research", summary="Retrieve relevant Maine authority")
def research(payload: dict):
    source_cards = payload.get("source_cards") or []
    source_card_store = SourceCardStore()
    for card in source_cards:
        source_card_store.add(card)
    return review_response(
        "POST /api/research",
        "authority_research",
        {
            "status": "review_required",
            "query": payload.get("query"),
            "retrieved_sources": payload.get("retrieved_sources", []),
            "source_cards": source_cards,
            "source_card_count": len(source_cards),
            "message": "Retrieval stack is available; production authority corpus must be ingested before authoritative answers.",
        },
    )
