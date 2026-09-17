"""Canonical, device-scoped setup routes for optional local AI.

General-purpose Qwen setup requires an explicit consent-bound plan and pinned
artifacts. Specialist admission remains separate; setup never certifies legal
quality. Ordinary status reads do not probe or start an inference engine.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool, StrictInt

from app.api.security import review_response
from legal.local_ai import LocalAiCatalog, LocalAiCatalogError, LocalAiSetupError, LocalAiSetupStore
from legal.security.local_request_firewall import evaluate_local_request


router = APIRouter(tags=["local-ai-setup"])
_ALLOWED_ROLES = {"reviewer", "attorney", "admin", "paralegal"}
_TENANT_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:-]{0,78}[A-Za-z0-9])?\Z")
_SESSION_RE = re.compile(r"[a-f0-9]{32,64}\Z")


class BasicModeRequest(BaseModel):
    expected_revision: StrictInt = Field(ge=0, le=1_000_000)
    user_confirmed: StrictBool


class CatalogAssessmentRequest(BaseModel):
    profile_id: str | None = Field(default=None, min_length=3, max_length=80)


class InstallPlanRequest(BaseModel):
    profile_id: str = Field(min_length=3, max_length=80)


def _guard(
    request: Request,
    role: str | None,
    tenant_id: str | None,
    client_session_id: str | None,
) -> tuple[str, str, str]:
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
    safe_role = str(role or "").strip().casefold()
    safe_tenant = str(tenant_id or "").strip()
    safe_session = str(client_session_id or "").strip().casefold()
    if safe_role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="local_ai_setup_role_required")
    if not _TENANT_RE.fullmatch(safe_tenant):
        raise HTTPException(status_code=403, detail="local_ai_setup_tenant_required")
    if not _SESSION_RE.fullmatch(safe_session):
        raise HTTPException(status_code=403, detail="local_ai_setup_session_required")
    return safe_role, safe_tenant, safe_session


def _store(tenant: str, session_id: str) -> LocalAiSetupStore:
    # The store gets only an opaque tenant/session partition.  It never receives
    # a matter root, record text, source text, browser-provided path, or model URL.
    return LocalAiSetupStore(audience=f"{tenant}:{session_id}")


def _audit_id(request: Request) -> str:
    return str(getattr(request.state, "mfll_audit_event_id", "local"))[:128]


def _respond(handler, *args: Any, endpoint: str, action: str, **kwargs: Any) -> dict[str, Any]:
    try:
        value = handler(*args, **kwargs)
    except (LocalAiSetupError, LocalAiCatalogError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return review_response(endpoint, action, value)


@router.get("/local-ai/setup/status", summary="Read local-only optional AI setup and hardware recommendation")
def status(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> dict[str, Any]:
    _role, tenant, session_id = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    return _respond(
        _store(tenant, session_id).status,
        endpoint="GET /api/local-ai/setup/status",
        action="local_ai_setup_status",
    )


@router.post("/local-ai/setup/basic-mode", summary="Confirm basic local-only operating mode")
def choose_basic_mode(
    payload: BasicModeRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> dict[str, Any]:
    _role, tenant, session_id = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    return _respond(
        _store(tenant, session_id).choose_basic_mode,
        expected_revision=payload.expected_revision,
        user_confirmed=payload.user_confirmed,
        audit_event_id=_audit_id(request),
        endpoint="POST /api/local-ai/setup/basic-mode",
        action="local_ai_setup_basic_mode_selected",
    )


@router.get("/local-ai/setup/catalog", summary="Read the cached, release-controlled local AI catalog")
def catalog(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> dict[str, Any]:
    _role, _tenant, _session_id = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    return _respond(
        LocalAiCatalog().status,
        endpoint="GET /api/local-ai/setup/catalog",
        action="local_ai_setup_catalog_read",
    )


@router.post("/local-ai/setup/assess", summary="Assess this device without downloading, starting, or probing a model")
def assess(
    payload: CatalogAssessmentRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> dict[str, Any]:
    _role, tenant, session_id = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    if payload.profile_id:
        return _respond(
            _store(tenant, session_id).assess_profile,
            payload.profile_id,
            endpoint="POST /api/local-ai/setup/assess",
            action="local_ai_setup_profile_assess",
        )
    return _respond(
        _store(tenant, session_id).status,
        endpoint="POST /api/local-ai/setup/assess",
        action="local_ai_setup_assess",
    )


@router.post("/local-ai/setup/plans", summary="Request a release-controlled local AI install plan")
def plan_install(
    payload: InstallPlanRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> dict[str, Any]:
    _role, _tenant, _session_id = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    # Do not expose an incomplete downloader as an install plan.  The profile
    # check preserves an exact 404 for unknown/future candidate names, while a
    # known future profile remains explicitly blocked until the verified engine
    # importer and transfer owner are included and qualified.
    _respond(
        LocalAiCatalog().profile,
        payload.profile_id,
        endpoint="POST /api/local-ai/setup/plans",
        action="local_ai_setup_plan_requested",
    )
    raise HTTPException(status_code=409, detail="local_ai_install_path_not_available")


# General-purpose Qwen setup is distinct from production-admitted specialist
# packs. Never mark the empty specialist catalog admitted merely to install it.
class ReasoningPrepareRequest(BaseModel):
    model: str = Field(min_length=1, max_length=32)


class ReasoningInstallRequest(BaseModel):
    plan_token: str = Field(min_length=32, max_length=128)
    user_confirmed: StrictBool


def _installation_store(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_mfll_client_session: str | None = Header(default=None, alias="X-MFLL-Client-Session"),
) -> LocalAiSetupStore:
    _role, tenant, session = _guard(request, x_user_role, x_tenant_id, x_mfll_client_session)
    return _store(tenant, session)


@router.post("/local-ai/installation/prepare")
def prepare_reasoning(payload: ReasoningPrepareRequest, store=Depends(_installation_store)):
    from legal.local_ai.installer import INSTALLS
    return _respond(INSTALLS.prepare, store, payload.model,
                    endpoint="POST /api/local-ai/installation/prepare", action="local_ai_install_prepare")


@router.post("/local-ai/installation/start")
def install_reasoning(payload: ReasoningInstallRequest, store=Depends(_installation_store)):
    from legal.local_ai.installer import INSTALLS
    return _respond(INSTALLS.start, store, payload.plan_token, payload.user_confirmed,
                    endpoint="POST /api/local-ai/installation/start", action="local_ai_install_confirmed")


@router.get("/local-ai/installation/jobs/{job_id}")
def reasoning_install_status(job_id: str, store=Depends(_installation_store)):
    from legal.local_ai.installer import INSTALLS
    return _respond(INSTALLS.status, store, job_id,
                    endpoint="GET /api/local-ai/installation/jobs/{job_id}", action="local_ai_install_status")


@router.post("/local-ai/installation/jobs/{job_id}/cancel")
def cancel_reasoning_install(job_id: str, store=Depends(_installation_store)):
    from legal.local_ai.installer import INSTALLS
    return _respond(INSTALLS.cancel, store, job_id,
                    endpoint="POST /api/local-ai/installation/jobs/{job_id}/cancel", action="local_ai_install_cancel")
