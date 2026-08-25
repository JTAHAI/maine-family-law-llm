from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictBool

from app.api.security import review_response, strict_json_bool
from app.services import AuthorityLibraryService, AuthorityProductService

router = APIRouter(tags=["authority"])


class AuthorityUpdateRequest(BaseModel):
    dry_run: StrictBool = False
    fixture_mode: StrictBool = False
    allow_live: StrictBool = False
    network_acknowledged: StrictBool = False
    force_refresh: StrictBool = False
    source_classes: list[str] = Field(default_factory=list)
    max_targets: int | None = None


@router.get("/authority/status", summary="Report the active verified local authority generation")
def authority_status():
    payload = AuthorityLibraryService().status()
    return review_response("GET /api/authority/status", "authority_status", payload)


@router.get("/authority/builds", summary="List verified authority builds")
def authority_builds(limit: int = 20):
    payload = AuthorityLibraryService().list_builds(limit=limit)
    return review_response("GET /api/authority/builds", "authority_builds", payload)


@router.get("/authority/sources", summary="Browse the Maine authority library")
def authority_sources(
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
    return review_response("GET /api/authority/sources", "authority_source_library", payload)


@router.get("/authority/sources/{source_id}", summary="Fetch one source record and source card")
def authority_source(source_id: str):
    payload = AuthorityLibraryService().get_source(source_id)
    return review_response("GET /api/authority/sources/{source_id}", "authority_source_detail", payload)


@router.get("/authority/sources/{source_id}/span", summary="Inspect an exact source span")
def authority_source_span(source_id: str, start_offset: int | None = None, end_offset: int | None = None):
    payload = AuthorityLibraryService().get_source_span(source_id, start_offset=start_offset, end_offset=end_offset)
    return review_response("GET /api/authority/sources/{source_id}/span", "authority_source_span", payload)


@router.get("/authority/update-report/{build_id}", summary="Fetch a prior authority update report")
def authority_update_report(build_id: str):
    payload = AuthorityLibraryService().get_update_report(build_id)
    return review_response("GET /api/authority/update-report/{build_id}", "authority_update_report", payload)


@router.post("/authority/update", summary="Update official Maine sources")
def authority_update(payload: AuthorityUpdateRequest):
    library = AuthorityLibraryService()
    if payload.allow_live and not payload.dry_run and not payload.network_acknowledged:
        return review_response(
            "POST /api/authority/update",
            "authority_update",
            {
                "status": "blocked",
                "review_required": True,
                "blockers": ["network_acknowledgement_required"],
                "message": "Live official-source updates require an explicit network acknowledgement.",
            },
        )
    result = library.update(
        dry_run=bool(payload.dry_run),
        source_classes=payload.source_classes,
        fixture_mode=bool(payload.fixture_mode),
        force_refresh=bool(payload.force_refresh),
        allow_live=bool(payload.allow_live),
        max_targets=payload.max_targets,
    )
    return review_response("POST /api/authority/update", "authority_update", result)


@router.post("/authority/update/cancel", summary="Cancel the current authority update")
def authority_update_cancel(payload: dict | None = None):
    job_id = str((payload or {}).get("job_id") or "").strip() or None
    result = AuthorityLibraryService().cancel_update(job_id)
    return review_response("POST /api/authority/update/cancel", "authority_update_cancel", result)


@router.post("/authority/citations/resolve", summary="Resolve citation variants against the active authority generation")
def resolve_active_authority_citations(payload: dict):
    try:
        result = AuthorityProductService().resolve_citations(str(payload.get("text") or ""))
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["active_authority_product_unavailable_or_unverified"],
            "resolutions": [],
            "review_required": True,
        }
    return review_response("POST /api/authority/citations/resolve", "authority_citation_resolution", result)


@router.post("/authority/pinpoints/resolve", summary="Resolve an exact admitted pinpoint without determining legal effect")
def resolve_active_authority_pinpoints(payload: dict):
    """Compatibility-stable pinpoint surface over the same immutable source index.

    Authority is a public source lane, so no private matter content is accepted
    or persisted here.  Every result is explicitly review-required and its
    exact offset is available only when the parsed authority record admitted it.
    """
    try:
        result = AuthorityProductService().resolve_citations(str(payload.get("text") or ""))
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["active_authority_product_unavailable_or_unverified"],
            "resolutions": [],
            "review_required": True,
        }
    result["boundary"] = (
        "A pinpoint locates admitted source text only. It does not determine legal effect, "
        "currentness, controlling authority, or a result in any matter."
    )
    return review_response("POST /api/authority/pinpoints/resolve", "authority_pinpoint_resolution", result)

@router.post("/authority/verify-output", summary="Verify an answer against the active immutable authority generation")
def verify_active_authority_output(payload: dict):
    try:
        result = AuthorityProductService().verify_output(
            text=str(payload.get("text") or ""),
            source_ids=payload.get("source_ids") or [],
            quotes=payload.get("quotes") or [],
            claims=payload.get("claims") or [],
            expected_jurisdiction=str(payload.get("expected_jurisdiction") or "maine"),
            auto_extract_claims=strict_json_bool(payload, "auto_extract_claims", default=True),
        )
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["active_authority_product_unavailable_or_unverified"],
            "review_required": True,
        }
    return review_response("POST /api/authority/verify-output", "authority_output_verification", result)
