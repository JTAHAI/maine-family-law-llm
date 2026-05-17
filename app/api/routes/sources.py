from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response

router = APIRouter(tags=["sources"])


@router.get("/sources/{source_id}", summary="Fetch an admitted source card or source text")
def get_source(source_id: str):
    return review_response(
        "GET /api/sources/{source_id}",
        "source_lookup",
        {
            "source_id": source_id,
            "source_card": {
                "source_id": source_id,
                "jurisdiction": "maine",
                "authority_status": "stale_unknown",
                "freshness_status": "unknown",
            },
            "source_text": None,
            "message": "Source text is only returned after official authority ingestion populates the external source store.",
        },
    )
