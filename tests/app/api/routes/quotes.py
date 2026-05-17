from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier

router = APIRouter(tags=["verification"])


@router.post("/quotes/verify", summary="Verify quoted source spans")
def verify_quotes(payload: dict):
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
    return review_response(
        "POST /api/quotes/verify",
        "quote_span_verification",
        {
            "quote_results": results,
            "source_text_available": bool(source_text),
        },
    )
