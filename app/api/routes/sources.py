from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from app.services import AuthorityLibraryService

router = APIRouter(tags=["sources"])


@router.get("/sources", summary="Browse the Maine authority library")
def list_sources(
    query: str = "",
    source_class: str = "",
    freshness: str = "",
    issue_tag: str = "",
    limit: int = 100,
    offset: int = 0,
):
    payload = AuthorityLibraryService().list_sources(
        query=query,
        source_class=source_class,
        freshness=freshness,
        issue_tag=issue_tag,
        limit=limit,
        offset=offset,
    )
    return review_response("GET /api/sources", "source_library", payload)


@router.get("/sources/{source_id}", summary="Fetch an admitted source card or bounded source text")
def get_source(source_id: str):
    payload = AuthorityLibraryService().get_source(source_id)
    return review_response("GET /api/sources/{source_id}", "source_lookup", payload)
