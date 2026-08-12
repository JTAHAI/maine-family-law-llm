from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.provider_connections import ProviderConnectionService
from legal.provider_connections.service import ProviderConnectionError
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["privacy"])


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


@router.post("/privacy/disconnect-all", summary="Disconnect all connected providers")
def disconnect_all(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().disconnect_all, action="privacy_disconnect_all", endpoint="POST /api/privacy/disconnect-all")


@router.post("/privacy/revoke-all", summary="Revoke all provider credentials")
def revoke_all(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_service().revoke_all, action="privacy_revoke_all", endpoint="POST /api/privacy/revoke-all")
