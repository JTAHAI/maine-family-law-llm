from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.provider_connections import ProviderConnectionService
from legal.provider_connections.service import ProviderConnectionError
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["providers"])


def _require_role(role: str | None, *, admin_only: bool = False) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
    if admin_only and normalized != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")


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


def _service() -> ProviderConnectionService:
    project_root = _project_root()
    store_root = os.environ.get("MFL_PROVIDER_STORE_ROOT") or None
    return ProviderConnectionService(project_root=project_root, store_root=store_root)


def _handle_error(exc: ProviderConnectionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except ProviderConnectionError as exc:
        raise _handle_error(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return review_response(endpoint, action, result)


@router.get("/providers", summary="List supported provider connections")
def list_providers(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    payload = {"providers": _service().list_providers(), "local_only": True, "review_required": True}
    return review_response("GET /api/providers", "providers_list", payload)


@router.post("/providers/{provider_id}/connect", summary="Connect a BYOK provider")
def connect_provider(
    provider_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().connect, provider_id, payload, action="providers_connect", endpoint="POST /api/providers/{provider_id}/connect")


@router.post("/providers/{provider_id}/disconnect", summary="Disconnect a provider")
def disconnect_provider(
    provider_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().disconnect, provider_id, action="providers_disconnect", endpoint="POST /api/providers/{provider_id}/disconnect")


@router.post("/providers/{provider_id}/health", summary="Check provider readiness without background traffic")
def health_provider(
    provider_id: str,
    request: Request,
    payload: dict[str, Any] | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    local_only = True if payload is None else bool(payload.get("local_only", True))
    return _invoke(_service().health, provider_id, local_only=local_only, action="providers_health", endpoint="POST /api/providers/{provider_id}/health")


@router.get("/providers/{provider_id}/capabilities", summary="Fetch provider capability report")
def provider_capabilities(provider_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().capabilities, provider_id, action="providers_capabilities", endpoint="GET /api/providers/{provider_id}/capabilities")


@router.get("/providers/{provider_id}/status", summary="Fetch provider status and sharing summary")
def provider_status(provider_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().provider_status, provider_id, action="providers_status", endpoint="GET /api/providers/{provider_id}/status")


@router.get("/providers/sharing-summary", summary="Fetch the current provider sharing summary")
def sharing_summary(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().sharing_summary, action="providers_sharing_summary", endpoint="GET /api/providers/sharing-summary")


@router.post("/providers/disconnect-all", summary="Disconnect all connected providers")
def disconnect_all(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().disconnect_all, action="providers_disconnect_all", endpoint="POST /api/providers/disconnect-all")


@router.post("/providers/revoke-all", summary="Revoke all provider credentials")
def revoke_all(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().revoke_all, action="providers_revoke_all", endpoint="POST /api/providers/revoke-all")


@router.post("/providers/return-local-only", summary="Return all provider sessions to local-only mode")
def return_local_only(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().return_local_only, action="providers_return_local_only", endpoint="POST /api/providers/return-local-only")
