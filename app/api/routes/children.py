from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.child_continuity import ChildContinuityError, ChildContinuityStore
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["children"])


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


def _project_root() -> Path:
    return Path(os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[3])


def _store() -> ChildContinuityStore:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        raise ChildContinuityError("active_case_unavailable", "The active case workspace is unavailable.", status_code=409)
    return ChildContinuityStore(case_root)


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _handle_error(exc: ChildContinuityError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except ChildContinuityError as exc:
        raise _handle_error(exc) from exc
    return review_response(endpoint, action, result)


@router.get("/children", summary="List child continuity profiles")
def list_children(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().list_children, action="children_list", endpoint="GET /api/children")


@router.post("/children", summary="Create a child continuity profile")
def create_child(
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().create_child, payload, action="children_create", endpoint="POST /api/children")


@router.get("/children/{child_id}", summary="Fetch a child continuity profile")
def get_child(
    child_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().get_child, child_id, action="children_get", endpoint="GET /api/children/{child_id}")


@router.patch("/children/{child_id}", summary="Update a child continuity profile")
def patch_child(
    child_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().patch_child, child_id, payload, action="children_patch", endpoint="PATCH /api/children/{child_id}")


@router.get("/children/{child_id}/continuity", summary="Fetch the child continuity summary")
def get_continuity(
    child_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().continuity, child_id, action="children_continuity", endpoint="GET /api/children/{child_id}/continuity")


@router.post("/children/{child_id}/continuity/build", summary="Build a child continuity snapshot")
def build_continuity(
    child_id: str,
    request: Request,
    payload: dict[str, Any] | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().build_continuity, child_id, payload or {}, action="children_continuity_build", endpoint="POST /api/children/{child_id}/continuity/build")


@router.post("/children/{child_id}/events", summary="Add a child continuity event")
def add_event(
    child_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().add_event, child_id, payload, action="children_event_add", endpoint="POST /api/children/{child_id}/events")


@router.patch("/children/{child_id}/events/{event_id}", summary="Update a child continuity event")
def patch_event(
    child_id: str,
    event_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().patch_event, child_id, event_id, payload, action="children_event_patch", endpoint="PATCH /api/children/{child_id}/events/{event_id}")


@router.get("/children/{child_id}/school", summary="Fetch child school continuity items")
def get_school(child_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().school, child_id, action="children_school", endpoint="GET /api/children/{child_id}/school")


@router.get("/children/{child_id}/care", summary="Fetch child care continuity items")
def get_care(child_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().care, child_id, action="children_care", endpoint="GET /api/children/{child_id}/care")


@router.get("/children/{child_id}/services", summary="Fetch child services continuity items")
def get_services(child_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().services, child_id, action="children_services", endpoint="GET /api/children/{child_id}/services")


@router.get("/children/{child_id}/gaps", summary="Fetch child continuity gaps")
def get_gaps(child_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().gaps, child_id, action="children_gaps", endpoint="GET /api/children/{child_id}/gaps")


@router.post("/children/{child_id}/schedule-scenarios", summary="Build neutral schedule scenarios")
def build_schedule_scenarios(
    child_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().build_schedule_scenarios, child_id, payload, action="children_schedule_scenarios", endpoint="POST /api/children/{child_id}/schedule-scenarios")


@router.post("/children/{child_id}/claims/review", summary="Review child continuity claims and contradictions")
def review_claims(
    child_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().review_claims, child_id, payload, action="children_claims_review", endpoint="POST /api/children/{child_id}/claims/review")


@router.post("/children/{child_id}/packet", summary="Export a child-focused continuity packet")
def export_packet(
    child_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().packet, child_id, payload, action="children_packet", endpoint="POST /api/children/{child_id}/packet")
