"""Canonical, tenant- and matter-scoped routes for the v8 Add-on Studio."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api.security import review_response
from legal.addons import ADDON_IDS, AddonStudioError, AddonStudioStore
from legal.security.local_request_firewall import evaluate_local_request


router = APIRouter(tags=["addon-studio"])
_ALLOWED_ROLES = {"reviewer", "attorney", "admin", "paralegal"}
_TENANT = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?\Z")


def _guard(request: Request, role: str | None, tenant_id: str | None) -> tuple[str, str]:
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
    safe_role = (role or "").strip().casefold()
    safe_tenant = (tenant_id or "").strip().casefold()
    if safe_role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
    if not _TENANT.fullmatch(safe_tenant):
        raise HTTPException(status_code=403, detail="tenant_scope_required")
    return safe_role, safe_tenant


def _store(tenant_id: str) -> AddonStudioStore:
    import maine_family_law_llm.api as main_api

    case_root = main_api.active_case_root()
    if case_root is None:
        raise AddonStudioError(
            "active_case_unavailable",
            "Select an active matter before opening Add-on Studio.",
            status_code=409,
        )
    return AddonStudioStore(case_root, tenant_id=tenant_id)


def _audit_id(request: Request) -> str:
    return str(getattr(request.state, "mfll_audit_event_id", "local"))


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        value = handler(*args, **kwargs)
    except AddonStudioError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return review_response(endpoint, action, value)


@router.get("/addons", summary="Fetch the matter Add-on Studio")
def summary(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _role, tenant = _guard(request, x_user_role, x_tenant_id)
    return _invoke(_store(tenant).summary, action="addon_summary", endpoint="GET /api/addons")


@router.post("/addons/{addon_id}/actions", summary="Run one review-required add-on action")
def execute(
    addon_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    role, tenant = _guard(request, x_user_role, x_tenant_id)
    if addon_id not in ADDON_IDS:
        raise HTTPException(status_code=404, detail="addon_not_found")
    return _invoke(
        _store(tenant).execute,
        addon_id,
        payload,
        actor_role=role,
        audit_event_id=_audit_id(request),
        action=f"addon_{addon_id}_execute",
        endpoint="POST /api/addons/{addon_id}/actions",
    )


@router.get("/addons/integrity", summary="Verify the add-on result and audit hash chain")
def integrity(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _role, tenant = _guard(request, x_user_role, x_tenant_id)
    return _invoke(
        _store(tenant).verify_integrity,
        action="addon_integrity_verify",
        endpoint="GET /api/addons/integrity",
    )


@router.get("/addons/{addon_id}/results/{result_id}", summary="Inspect an exact add-on result")
def result(
    addon_id: str,
    result_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _role, tenant = _guard(request, x_user_role, x_tenant_id)
    return _invoke(
        _store(tenant).item,
        addon_id,
        result_id,
        action="addon_result_inspect",
        endpoint="GET /api/addons/{addon_id}/results/{result_id}",
    )


@router.post(
    "/addons/{addon_id}/results/{result_id}/review",
    summary="Record an immutable human review decision",
)
def review_result(
    addon_id: str,
    result_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    role, tenant = _guard(request, x_user_role, x_tenant_id)
    return _invoke(
        _store(tenant).review_result,
        addon_id,
        result_id,
        payload,
        actor_role=role,
        audit_event_id=_audit_id(request),
        action="addon_result_review",
        endpoint="POST /api/addons/{addon_id}/results/{result_id}/review",
    )


@router.get(
    "/addons/{addon_id}/results/{result_id}/artifacts/{artifact_id}",
    summary="Open an exact decrypted add-on artifact",
)
def artifact(
    addon_id: str,
    result_id: str,
    artifact_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Response:
    _role, tenant = _guard(request, x_user_role, x_tenant_id)
    try:
        metadata, content = _store(tenant).artifact_content(addon_id, result_id, artifact_id)
    except AddonStudioError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    response = Response(
        content=content,
        media_type=str(metadata.get("media_type") or "application/octet-stream"),
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{metadata["download_name"]}"'
    )
    response.headers["X-Content-SHA256"] = str(metadata.get("content_sha256") or "")
    response.headers["X-MFLL-Review-Required"] = "true"
    return response
