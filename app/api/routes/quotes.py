from __future__ import annotations

from fastapi import APIRouter, Header

from app.api.security import review_response
from app.services import ConversationAdapter
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier

router = APIRouter(tags=["verification"])
adapter = ConversationAdapter()


@router.post("/quotes/verify", summary="Verify quoted source spans")
def verify_quotes(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    verifier = QuoteSpanVerifier()
    source_text = payload.get("source_text", "")
    quotes = payload.get("quotes") or [payload.get("quoted_text", "")]
    source_id = payload.get("source_id")
    results = []
    for quote in quotes:
        quoted_text = quote.get("quoted_text", "") if isinstance(quote, dict) else quote
        result = verifier.verify(source_text, quoted_text)
        if source_id:
            result["source_id"] = source_id
        results.append(result)
    response = adapter.for_quote_verification(
        payload,
        {
            "quote_results": results,
            "source_text_available": bool(source_text),
        },
        audience_hint=x_user_role,
    )
    return review_response("POST /api/quotes/verify", "quote_span_verification", response)
