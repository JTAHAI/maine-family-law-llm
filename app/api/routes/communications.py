from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.communications.workbench import CommunicationsWorkbenchError, CommunicationsWorkbenchStore
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["communications"])


def _require_role(role: str | None) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")


def _enforce_local_request(request: Request) -> None:
    decision = evaluate_local_request(
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else None,
        host_header=request.headers.get("host", ""),
        origin_header=request.headers.get("origin", ""),
        sec_fetch_site=request.headers.get("sec-fetch-site", ""),
        content_length=request.headers.get("content-length", ""),
    )
    if not decision.allowed:
        raise HTTPException(status_code=decision.status_code, detail=decision.code)


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _store() -> CommunicationsWorkbenchStore:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        raise CommunicationsWorkbenchError("active_case_unavailable", "The active case workspace is unavailable.", status_code=409)
    return CommunicationsWorkbenchStore(case_root)


def _handle_error(exc: CommunicationsWorkbenchError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except CommunicationsWorkbenchError as exc:
        raise _handle_error(exc) from exc
    return review_response(endpoint, action, result)


@router.get("/communications", summary="Fetch the communications and parenting-time workbench")
def get_communications(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().summary, action="communications_summary", endpoint="GET /api/communications")


@router.post("/communications/import", summary="Import local communications records")
def import_communications(
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().import_communications, payload, action="communications_import", endpoint="POST /api/communications/import")


@router.get("/communications/messages", summary="List imported communications messages")
def list_messages(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().list_messages, limit=limit, offset=offset, action="communications_messages", endpoint="GET /api/communications/messages")


@router.get("/communications/threads", summary="List reconstructed communications threads")
def list_threads(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().list_threads, limit=limit, offset=offset, action="communications_threads", endpoint="GET /api/communications/threads")


@router.get("/communications/schedule", summary="Fetch schedule change history")
def get_schedule_history(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().schedule, action="communications_schedule", endpoint="GET /api/communications/schedule")


@router.get("/communications/parenting-time", summary="Fetch parenting-time event review")
def get_parenting_time(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().parenting_time, action="communications_parenting_time", endpoint="GET /api/communications/parenting-time")


@router.get("/communications/agreements", summary="Fetch agreement and dispute mappings")
def get_agreements(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().agreements, action="communications_agreements", endpoint="GET /api/communications/agreements")


@router.get("/communications/claims", summary="Fetch communication claims")
def get_claims(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().claims, action="communications_claims", endpoint="GET /api/communications/claims")


@router.get("/communications/completeness", summary="Fetch communication completeness")
def get_completeness(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().completeness, action="communications_completeness", endpoint="GET /api/communications/completeness")


@router.get("/communications/review-history", summary="Fetch communications review history")
def get_review_history(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().review_history, limit=limit, offset=offset, action="communications_review_history", endpoint="GET /api/communications/review-history")


@router.post("/communications/exports", summary="Export a communications review bundle")
def export_bundle(
    request: Request,
    payload: dict[str, Any] | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    format_name = str((payload or {}).get("format") or "json")
    return _invoke(_store().export_bundle, format_name=format_name, action="communications_export", endpoint="POST /api/communications/exports")
