"""Canonical routes for the ten matter productivity capabilities."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.productivity import ProductivitySuiteError, ProductivitySuiteStore
from legal.security.local_request_firewall import evaluate_local_request


router = APIRouter(tags=["productivity-studio"])


def _require_role(role: str | None, *, admin_only: bool = False) -> None:
    normalized = (role or "").strip().lower()
    allowed = {"admin"} if admin_only else {"reviewer", "attorney", "admin", "paralegal"}
    if normalized not in allowed:
        raise HTTPException(status_code=403, detail="admin_role_required" if admin_only else "reviewer_role_required")


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


def _store() -> ProductivitySuiteStore:
    import maine_family_law_llm.api as main_api

    case_root = main_api.active_case_root()
    if case_root is None:
        raise ProductivitySuiteError(
            "active_case_unavailable", "Select an active matter before opening Productivity Studio.", status_code=409
        )
    return ProductivitySuiteStore(case_root)


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except ProductivitySuiteError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return review_response(endpoint, action, result)


def _guard(request: Request, role: str | None, *, admin_only: bool = False) -> None:
    _enforce_local_request(request)
    _require_role(role, admin_only=admin_only)


@router.get("/productivity", summary="Fetch the matter Productivity Studio")
def summary(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().summary(), action="productivity_summary", endpoint="GET /api/productivity")


@router.post("/productivity/inbox/configurations", summary="Configure a safe matter inbox")
def configure_inbox(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().configure_inbox(payload), action="productivity_inbox_configure", endpoint="POST /api/productivity/inbox/configurations")


@router.post("/productivity/inbox/{inbox_id}/scan", summary="Review candidate inbox records")
def scan_inbox(inbox_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().scan_inbox(inbox_id, payload), action="productivity_inbox_scan", endpoint="POST /api/productivity/inbox/{inbox_id}/scan")


@router.post("/productivity/recipes", summary="Save a local workflow recipe")
def save_recipe(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().save_recipe(payload), action="productivity_recipe_save", endpoint="POST /api/productivity/recipes")


@router.post("/productivity/recipes/{recipe_id}/run", summary="Run a confirmed local workflow recipe")
def run_recipe(recipe_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().run_recipe(recipe_id, payload), action="productivity_recipe_run", endpoint="POST /api/productivity/recipes/{recipe_id}/run")


@router.post("/productivity/calendar/exports", summary="Create a review-required ICS export")
def export_calendar(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().export_calendar(payload), action="productivity_calendar_export", endpoint="POST /api/productivity/calendar/exports")


@router.post("/productivity/hardware/optimize", summary="Create a hardware-safe local execution plan")
def optimize_hardware(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().optimize_hardware(payload), action="productivity_hardware_optimize", endpoint="POST /api/productivity/hardware/optimize")


@router.post("/productivity/pinboard/items", summary="Pin an exact source span")
def add_pinboard_item(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().add_pinboard_item(payload), action="productivity_pinboard_add", endpoint="POST /api/productivity/pinboard/items")


@router.post("/productivity/redaction/projects", summary="Create a redaction review project")
def create_redaction_project(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().create_redaction_project(payload), action="productivity_redaction_project", endpoint="POST /api/productivity/redaction/projects")


@router.post("/productivity/redaction/projects/{project_id}/finalize", summary="Create a reviewed redacted derivative")
def finalize_redaction_project(project_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().finalize_redaction_project(project_id, payload), action="productivity_redaction_finalize", endpoint="POST /api/productivity/redaction/projects/{project_id}/finalize")


@router.post("/productivity/next-actions/refresh", summary="Build the matter next-action review queue")
def refresh_next_actions(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().refresh_next_actions(payload), action="productivity_next_actions", endpoint="POST /api/productivity/next-actions/refresh")


@router.post("/productivity/courtroom/sessions", summary="Create a source-bound courtroom presentation")
def create_courtroom_session(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().create_courtroom_session(payload), action="productivity_courtroom_session", endpoint="POST /api/productivity/courtroom/sessions")


@router.post("/productivity/backups/schedules", summary="Configure encrypted matter backups")
def save_backup_schedule(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().save_backup_schedule(payload), action="productivity_backup_schedule", endpoint="POST /api/productivity/backups/schedules")


@router.post("/productivity/backups/run", summary="Run and verify an encrypted matter backup")
def run_backup(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().run_backup(payload), action="productivity_backup_run", endpoint="POST /api/productivity/backups/run")


@router.get("/productivity/backups", summary="Browse safe metadata for encrypted matter snapshots")
def list_backups(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().list_backups(), action="productivity_backup_list", endpoint="GET /api/productivity/backups")


@router.get("/productivity/backups/{backup_id}/verify", summary="Verify an encrypted matter backup")
def verify_backup(backup_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().verify_backup(backup_id), action="productivity_backup_verify", endpoint="GET /api/productivity/backups/{backup_id}/verify")


@router.post("/productivity/backups/{backup_id}/restore", summary="Restore a backup into an isolated recovery directory")
def restore_backup(backup_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().restore_backup(backup_id, payload), action="productivity_backup_restore", endpoint="POST /api/productivity/backups/{backup_id}/restore")


@router.get("/productivity/sources/{item_id}", summary="Inspect an exact Productivity Studio source item")
def source_item(item_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _guard(request, x_user_role)
    return _invoke(lambda: _store().source_item(item_id), action="productivity_source_inspect", endpoint="GET /api/productivity/sources/{item_id}")
