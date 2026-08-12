from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.ops.release_control_center import ReleaseControlCenterService
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["release", "control-center"])


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


def _service() -> ReleaseControlCenterService:
    from maine_family_law_llm import api as main_api

    return ReleaseControlCenterService(
        _project_root(),
        case_root=main_api.active_case_root(),
        release_root=os.environ.get("MAINE_FAMILY_LAW_RELEASE_ROOT"),
        evidence_root=os.environ.get("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT"),
        pilot_root=os.environ.get("MAINE_FAMILY_LAW_PILOT_ROOT"),
    )


@router.get("/release-control-center/status", summary="Fetch the release control center status")
def status(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _enforce_local_request(request)
    payload = _service().status()
    payload["user_role"] = str(x_user_role or "viewer")
    payload["tenant_id"] = str(x_tenant_id or "tenant_unassigned")
    return review_response("GET /api/release-control-center/status", "release_control_center_status", payload)
