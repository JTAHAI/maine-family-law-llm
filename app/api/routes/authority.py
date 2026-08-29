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


class AuthorityBuildActivationRequest(BaseModel):
    build_id: str = Field(min_length=24, max_length=24)
    acknowledged: StrictBool = False


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


@router.get("/authority/builds/{build_id}/diff", summary="Compare a verified staged authority build to the active build")
def authority_build_diff(build_id: str):
    result = AuthorityLibraryService().compare_builds(build_id)
    return review_response("GET /api/authority/builds/{build_id}/diff", "authority_build_diff", result)


@router.post("/authority/activate", summary="Explicitly activate a verified staged authority build")
def authority_activate(payload: AuthorityBuildActivationRequest):
    if not payload.acknowledged:
        result = {
            "status": "blocked",
            "build_id": payload.build_id,
            "blockers": ["authority_activation_acknowledgement_required"],
            "review_required": True,
        }
    else:
        result = AuthorityLibraryService().activate_build(payload.build_id, operation="activate")
    return review_response("POST /api/authority/activate", "authority_build_activation", result)


@router.post("/authority/rollback", summary="Explicitly restore a prior verified authority build")
def authority_rollback(payload: AuthorityBuildActivationRequest):
    if not payload.acknowledged:
        result = {
            "status": "blocked",
            "build_id": payload.build_id,
            "blockers": ["authority_rollback_acknowledgement_required"],
            "review_required": True,
        }
    else:
        result = AuthorityLibraryService().activate_build(payload.build_id, operation="rollback")
    return review_response("POST /api/authority/rollback", "authority_build_rollback", result)


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


@router.get("/authority/gaps", summary="Review active authority metadata coverage gaps")
def authority_gaps(issue: str = ""):
    try:
        result = AuthorityProductService().authority_gap_review(issue=issue)
    except (FileNotFoundError, ValueError, OSError):
        result = {"status": "blocked", "blockers": ["active_authority_product_unavailable_or_unverified"], "review_required": True}
    return review_response("GET /api/authority/gaps", "authority_gap_review", result)


@router.get("/authority/gaps/sources/{source_id}", summary="Inspect a source in the reviewed authority build")
def authority_gap_source(source_id: str, build_id: str):
    try:
        result = AuthorityProductService().authority_gap_source(source_id, build_id=build_id)
    except (FileNotFoundError, ValueError, OSError):
        result = {"status": "blocked", "blockers": ["active_authority_product_unavailable_or_unverified"], "review_required": True}
    return review_response("GET /api/authority/gaps/sources/{source_id}", "authority_gap_source_review", result)


@router.get("/authority/freshness", summary="Review authority-source freshness and parser metadata")
def authority_freshness_dashboard():
    """Expose review signals without deciding legal currentness or completeness."""
    try:
        result = AuthorityLibraryService().freshness_dashboard()
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["authority_freshness_metadata_unavailable"],
            "review_required": True,
            "current_law_determined": False,
        }
    return review_response("GET /api/authority/freshness", "authority_freshness_dashboard", result)


@router.get("/authority/availability", summary="Review stored official-source availability evidence")
def authority_availability_monitor():
    """Review admitted metadata without probing, redirecting, or substituting sources."""
    try:
        result = AuthorityLibraryService().availability_monitor()
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["authority_availability_metadata_unavailable"],
            "review_required": True,
            "availability_determined": False,
            "network_used": False,
            "mirror_substitution": False,
        }
    return review_response("GET /api/authority/availability", "official_source_availability_monitor", result)


@router.get("/authority/parser-regression", summary="Run bundled synthetic parser-regression fixtures")
def authority_parser_regression():
    try:
        result = AuthorityLibraryService().parser_regression_corpus()
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["parser_regression_corpus_unavailable"],
            "review_required": True,
            "corpus_is_legal_authority": False,
            "network_used": False,
        }
    return review_response("GET /api/authority/parser-regression", "authority_parser_regression", result)


@router.get("/authority/parser-regression/{fixture_id}", summary="Inspect one synthetic parser-regression fixture receipt")
def authority_parser_regression_fixture(fixture_id: str):
    try:
        result = AuthorityLibraryService().parser_regression_fixture(fixture_id)
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "fixture_id": fixture_id[:160],
            "blockers": ["parser_regression_fixture_unavailable"],
            "review_required": True,
            "can_support_legal_claim": False,
        }
    return review_response("GET /api/authority/parser-regression/{fixture_id}", "authority_parser_regression_fixture", result)


@router.get("/authority/lineage/{source_id}", summary="Inspect one admitted source's immutable provenance lineage")
def authority_lineage(source_id: str):
    try:
        result = AuthorityProductService().authority_lineage(source_id)
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "source_id": source_id[:256],
            "blockers": ["active_authority_product_unavailable_or_unverified"],
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
        }
    return review_response("GET /api/authority/lineage/{source_id}", "authority_lineage_inspection", result)


@router.post("/authority/forms/synchronize", summary="Compare installed form metadata with the active admitted form catalog")
def authority_forms_synchronize(payload: dict):
    try:
        result = AuthorityProductService().synchronize_forms(payload.get("installed_forms"))
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "blockers": ["active_authority_form_catalog_unavailable_or_unverified"],
            "review_required": True,
            "completion_blocked": True,
            "network_used": False,
        }
    return review_response("POST /api/authority/forms/synchronize", "authority_form_catalog_synchronization", result)


@router.get("/authority/opinions/{source_id}/enrichment", summary="Inspect deterministic source-bound Law Court opinion metadata")
def authority_law_court_opinion_enrichment(source_id: str):
    try:
        result = AuthorityProductService().law_court_opinion_enrichment(source_id)
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "source_id": source_id[:256],
            "blockers": ["active_law_court_opinion_unavailable_or_unverified"],
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "treatment_determined": False,
        }
    return review_response("GET /api/authority/opinions/{source_id}/enrichment", "law_court_opinion_enrichment", result)


@router.get("/authority/rules/history", summary="Inspect admitted procedural or evidentiary rule history metadata")
def authority_rule_history_timeline(query: str = ""):
    try:
        result = AuthorityProductService().rule_history_timeline(query)
    except (FileNotFoundError, ValueError, OSError):
        result = {
            "status": "blocked",
            "query": query[:256],
            "timeline": [],
            "blockers": ["active_rule_history_unavailable_or_unverified"],
            "review_required": True,
            "network_used": False,
            "as_of_determined": False,
        }
    return review_response("GET /api/authority/rules/history", "rule_history_timeline_inspection", result)


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
