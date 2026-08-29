"""Protected canonical routes for authority-change impact revalidation.

Authority generations are public, but the set of saved work that refers to
them is private matter data.  These endpoints therefore bind every operation
to the currently active matter before they expose a document, deadline, form,
or review-packet identifier.
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool

from app.api.security import review_response
from app.services import AuthorityLibraryService
from legal.review import AuthorityChangeImpactStore, AuthorityImpactError


router = APIRouter(tags=["authority-impact"])


class AuthorityImpactAnalyzeRequest(BaseModel):
    base_build_id: str = Field(min_length=24, max_length=24)
    target_build_id: str = Field(min_length=24, max_length=24)


class AuthorityImpactBuildRequest(AuthorityImpactAnalyzeRequest):
    approved: StrictBool = False


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _matter_id(case_root: Path) -> str:
    return hashlib.sha256(str(case_root.resolve()).encode("utf-8")).hexdigest()[:16]


def _store(matter_id: str) -> AuthorityChangeImpactStore:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        raise HTTPException(
            status_code=409,
            detail={"error": "active_matter_unavailable", "message": "Select an active matter before reviewing authority impact."},
        )
    resolved_case_root = Path(case_root).resolve()
    # A nonmatching matter must be indistinguishable from an unavailable one.
    # This fails closed even if a caller knows another matter's identifier.
    if not hmac.compare_digest(str(matter_id or ""), _matter_id(resolved_case_root)):
        raise HTTPException(
            status_code=404,
            detail={"error": "authority_impact_matter_unavailable", "message": "The requested matter is unavailable."},
        )
    authority = AuthorityLibraryService()
    return AuthorityChangeImpactStore(
        resolved_case_root,
        data_root=authority.data_root,
        repo_root=authority.repo_root,
    )


def _audit_id(request: Request) -> str:
    return str(getattr(request.state, "mfll_audit_event_id", "local"))


def _invoke(
    *,
    store: AuthorityChangeImpactStore,
    handler,
    action: str,
    endpoint: str,
    role: str | None,
    tenant_id: str | None,
    audit_event_id: str,
    document_id: str = "",
    build_id: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        result = handler(**kwargs)
        receipt = store.record_access(
            action=action,
            actor_role=str(role or ""),
            tenant_id=str(tenant_id or ""),
            audit_event_id=audit_event_id,
            document_id=document_id,
            build_id=build_id,
        )
    except AuthorityImpactError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    result["access_receipt"] = receipt
    return review_response(endpoint, action, result)


@router.get(
    "/matters/{matter_id}/authority-change-impact/status",
    summary="List verified authority generations for one matter revalidation review",
)
def status(
    matter_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    store = _store(matter_id)
    return _invoke(
        store=store,
        handler=store.list_generations,
        action="authority_impact_status",
        endpoint="GET /api/matters/{matter_id}/authority-change-impact/status",
        role=x_user_role,
        tenant_id=x_tenant_id,
        audit_event_id=_audit_id(request),
    )


@router.post(
    "/matters/{matter_id}/authority-change-impact/analyze",
    summary="Map changed authority sources to saved matter work",
)
def analyze_matter(
    matter_id: str,
    payload: AuthorityImpactAnalyzeRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    store = _store(matter_id)
    return _invoke(
        store=store,
        handler=store.analyze_matter,
        action="authority_impact_matter_analyze",
        endpoint="POST /api/matters/{matter_id}/authority-change-impact/analyze",
        role=x_user_role,
        tenant_id=x_tenant_id,
        audit_event_id=_audit_id(request),
        base_build_id=payload.base_build_id,
        target_build_id=payload.target_build_id,
    )


@router.post(
    "/matters/{matter_id}/authority-change-impact/documents/{document_id}/analyze",
    summary="Map changed authority sources to one exact saved document",
)
def analyze_document(
    matter_id: str,
    document_id: str,
    payload: AuthorityImpactAnalyzeRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    store = _store(matter_id)
    return _invoke(
        store=store,
        handler=lambda: store.analyze_document(
            document_id, payload.base_build_id, payload.target_build_id
        ),
        action="authority_impact_document_analyze",
        endpoint="POST /api/matters/{matter_id}/authority-change-impact/documents/{document_id}/analyze",
        role=x_user_role,
        tenant_id=x_tenant_id,
        audit_event_id=_audit_id(request),
        document_id=document_id,
    )


@router.post(
    "/matters/{matter_id}/authority-change-impact/documents/{document_id}/packet",
    summary="Build an immutable review-required authority revalidation packet",
)
def build_packet(
    matter_id: str,
    document_id: str,
    payload: AuthorityImpactBuildRequest,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    store = _store(matter_id)
    return _invoke(
        store=store,
        handler=lambda: store.build(
            document_id,
            payload.base_build_id,
            payload.target_build_id,
            approved=payload.approved,
        ),
        action="authority_impact_packet_build",
        endpoint="POST /api/matters/{matter_id}/authority-change-impact/documents/{document_id}/packet",
        role=x_user_role,
        tenant_id=x_tenant_id,
        audit_event_id=_audit_id(request),
        document_id=document_id,
    )


@router.get(
    "/matters/{matter_id}/authority-change-impact/packets/{build_id}",
    summary="Inspect one exact authority revalidation packet",
)
def packet(
    matter_id: str,
    build_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    store = _store(matter_id)
    return _invoke(
        store=store,
        handler=lambda: store.active(build_id),
        action="authority_impact_packet_inspect",
        endpoint="GET /api/matters/{matter_id}/authority-change-impact/packets/{build_id}",
        role=x_user_role,
        tenant_id=x_tenant_id,
        audit_event_id=_audit_id(request),
        build_id=build_id,
    )
