from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_ENDPOINTS = {"/api/health", "/api/version"}
ALLOWED_ROLES = {"attorney", "reviewer", "admin", "paralegal"}
ADMIN_ONLY_PREFIXES = ("/api/admin",)


@dataclass(frozen=True)
class APIContext:
    user_role: str
    tenant_id: str
    audit_event_id: str
    public_endpoint: bool = False

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "user_role": self.user_role,
            "tenant_id": self.tenant_id,
            "audit_event_id": self.audit_event_id,
            "public_endpoint": self.public_endpoint,
        }


async def require_api_role(
    request: Request,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> APIContext:
    """Enforce a simple role/tenant header contract for protected API routes.

    This is intentionally deterministic for the standalone local product: real
    deployments can swap the header contract for OAuth/JWT while keeping the
    same endpoint-level gate semantics.
    """

    path = request.url.path
    event_id = str(uuid.uuid4())
    if path in PUBLIC_ENDPOINTS:
        return APIContext(
            user_role=x_user_role or "public",
            tenant_id=x_tenant_id or "public",
            audit_event_id=event_id,
            public_endpoint=True,
        )

    role = (x_user_role or "").strip().lower()
    tenant_id = (x_tenant_id or "").strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "rbac_role_required",
                "allowed_roles": sorted(ALLOWED_ROLES),
                "audit_event_id": event_id,
            },
        )
    if not tenant_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "tenant_scope_required", "audit_event_id": event_id},
        )
    if path.startswith(ADMIN_ONLY_PREFIXES) and role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_role_required", "audit_event_id": event_id},
        )

    return APIContext(user_role=role, tenant_id=tenant_id, audit_event_id=event_id)


class AuditHeaderMiddleware(BaseHTTPMiddleware):
    """Emit immutable-ish audit identifiers on every API response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        audit_event_id = request.headers.get("X-Audit-Event-Id") or str(uuid.uuid4())
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["X-MFLL-Audit-Event-Id"] = audit_event_id
            response.headers["X-MFLL-Audit-Event-Type"] = f"{request.method}:{request.url.path}"
            response.headers["X-MFLL-RBAC"] = "public" if request.url.path in PUBLIC_ENDPOINTS else "enforced"
        return response


def audit_event(endpoint: str, action: str, role: str = "contract", tenant_id: str = "contract") -> dict[str, str]:
    return {
        "event_id": str(uuid.uuid4()),
        "endpoint": endpoint,
        "action": action,
        "actor_role": role,
        "tenant_id": tenant_id,
        "audit_status": "emitted",
    }


def rbac_envelope(required_role: str = "attorney_or_reviewer", tenant_scoped: bool = True) -> dict[str, str | bool]:
    return {
        "enforced": True,
        "required_role": required_role,
        "tenant_scoped": tenant_scoped,
        "mode": "header_contract_replaceable_by_enterprise_auth_provider",
    }


def review_response(endpoint: str, action: str, payload: dict) -> dict:
    """Attach common API completion fields to deterministic endpoint responses."""

    payload.setdefault("review_required", True)
    payload.setdefault("rbac", rbac_envelope())
    payload.setdefault("audit_event", audit_event(endpoint, action))
    return payload
