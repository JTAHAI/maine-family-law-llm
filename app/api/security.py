from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from typing import Annotated

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_ENDPOINTS = {"/api/health", "/api/version"}
ALLOWED_ROLES = {"attorney", "reviewer", "admin", "paralegal"}
ADMIN_ONLY_PREFIXES = ("/api/admin",)
_TENANT_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?")
_SESSION_PURPOSE = "security_privacy_session_capability"
_CAPABILITY_REPLAY_LOCK = threading.RLock()
_CONSUMED_CAPABILITIES: dict[str, float] = {}


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


@dataclass(frozen=True)
class SessionCapability:
    token: str
    issued_at: str
    expires_at: str
    purpose: str
    user_role: str
    tenant_id: str
    matter_id: str
    action: str
    csrf_token: str
    capability_id: str
    resource_type: str
    resource_id: str
    single_use: bool

    def as_dict(self) -> dict[str, str]:
        return {
            "token": self.token,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "purpose": self.purpose,
            "user_role": self.user_role,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "action": self.action,
            "csrf_token": self.csrf_token,
            "capability_id": self.capability_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "single_use": self.single_use,
        }


def _server_audit_event_id(request: Request) -> str:
    """Return the server-generated request audit identifier.

    Client-provided identifiers are intentionally ignored.  The middleware owns
    audit identity so error payloads, response headers, and route context cannot
    diverge or be spoofed by a caller.
    """

    value = getattr(request.state, "mfll_audit_event_id", "")
    if value:
        return str(value)
    value = str(uuid.uuid4())
    request.state.mfll_audit_event_id = value
    return value


def _session_secret() -> bytes:
    seed = (
        os.environ.get("MFL_SESSION_SIGNING_SECRET")
        or os.environ.get("MFL_PROJECT_ROOT")
        or "maine-family-law-llm-local-session-secret"
    )
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _canonical_token_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def mint_session_capability(
    *,
    user_role: str,
    tenant_id: str,
    matter_id: str,
    action: str,
    ttl_seconds: int = 15 * 60,
    resource_type: str = "matter",
    resource_id: str | None = None,
    single_use: bool = True,
) -> SessionCapability:
    issued = datetime.now(UTC)
    expires = issued + timedelta(seconds=max(60, ttl_seconds))
    csrf_token = hashlib.sha256(
        f"{user_role}|{tenant_id}|{matter_id}|{action}|{issued.isoformat()}".encode("utf-8")
    ).hexdigest()[:32]
    payload = {
        "purpose": _SESSION_PURPOSE,
        "user_role": user_role,
        "tenant_id": tenant_id,
        "matter_id": matter_id,
        "action": action,
        "csrf_token": csrf_token,
        "capability_id": str(uuid.uuid4()),
        "resource_type": str(resource_type or "matter")[:80],
        "resource_id": str(resource_id if resource_id is not None else matter_id)[:256],
        "single_use": bool(single_use),
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
    }
    signature = hmac.new(_session_secret(), _canonical_token_payload(payload), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(_canonical_token_payload({**payload, "signature": signature})).decode("ascii")
    return SessionCapability(
        token=token,
        issued_at=payload["issued_at"],
        expires_at=payload["expires_at"],
        purpose=payload["purpose"],
        user_role=user_role,
        tenant_id=tenant_id,
        matter_id=matter_id,
        action=action,
        csrf_token=csrf_token,
        capability_id=payload["capability_id"],
        resource_type=payload["resource_type"],
        resource_id=payload["resource_id"],
        single_use=payload["single_use"],
    )


def _prune_consumed_capabilities(now: float | None = None) -> None:
    current = float(now if now is not None else time.time())
    with _CAPABILITY_REPLAY_LOCK:
        for capability_id, expires_at in list(_CONSUMED_CAPABILITIES.items()):
            if expires_at <= current:
                _CONSUMED_CAPABILITIES.pop(capability_id, None)


def validate_session_capability(
    token: str,
    *,
    expected_user_role: str,
    expected_tenant_id: str,
    expected_matter_id: str,
    expected_action: str,
    csrf_token: str | None = None,
    expected_resource_type: str | None = None,
    expected_resource_id: str | None = None,
    consume: bool = True,
) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=403, detail={"error": "session_capability_required"})
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise HTTPException(status_code=403, detail={"error": "session_capability_invalid"}) from exc
    signature = str(payload.pop("signature", ""))
    expected_signature = hmac.new(_session_secret(), _canonical_token_payload(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail={"error": "session_capability_tampered"})
    if payload.get("purpose") != _SESSION_PURPOSE:
        raise HTTPException(status_code=403, detail={"error": "session_capability_invalid"})
    if payload.get("user_role") != expected_user_role:
        raise HTTPException(status_code=403, detail={"error": "session_role_mismatch"})
    if payload.get("tenant_id") != expected_tenant_id:
        raise HTTPException(status_code=403, detail={"error": "session_tenant_mismatch"})
    if payload.get("matter_id") != expected_matter_id:
        raise HTTPException(status_code=403, detail={"error": "session_matter_mismatch"})
    if payload.get("action") != expected_action:
        raise HTTPException(status_code=403, detail={"error": "session_action_mismatch"})
    if expected_resource_type is not None and payload.get("resource_type") != expected_resource_type:
        raise HTTPException(status_code=403, detail={"error": "session_resource_type_mismatch"})
    if expected_resource_id is not None and payload.get("resource_id") != expected_resource_id:
        raise HTTPException(status_code=403, detail={"error": "session_resource_mismatch"})
    if csrf_token is not None and payload.get("csrf_token") != csrf_token:
        raise HTTPException(status_code=403, detail={"error": "csrf_token_mismatch"})
    try:
        expires_at = datetime.fromisoformat(str(payload.get("expires_at")))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail={"error": "session_capability_invalid"}) from exc
    if expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=403, detail={"error": "session_capability_expired"})
    if bool(payload.get("single_use")) and consume:
        capability_id = str(payload.get("capability_id") or "")
        if not capability_id:
            raise HTTPException(status_code=403, detail={"error": "session_capability_invalid"})
        _prune_consumed_capabilities()
        with _CAPABILITY_REPLAY_LOCK:
            if capability_id in _CONSUMED_CAPABILITIES:
                raise HTTPException(status_code=403, detail={"error": "session_capability_replayed"})
            _CONSUMED_CAPABILITIES[capability_id] = expires_at.timestamp()
    return payload


def _path_is_within_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def strict_json_bool(payload: dict[str, Any], field: str, *, default: bool) -> bool:
    """Read a safety-sensitive JSON boolean without truthy-string coercion."""

    if field not in payload:
        return default
    value = payload[field]
    if type(value) is not bool:  # bool is intentionally exact; integers are refused.
        raise HTTPException(
            status_code=422,
            detail={"error": "strict_json_boolean_required", "field": field},
        )
    return value


async def require_api_role(
    request: Request,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> APIContext:
    """Enforce a deterministic role and tenant contract for protected routes."""

    path = request.url.path
    event_id = _server_audit_event_id(request)
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
    if not _TENANT_ID_RE.fullmatch(tenant_id):
        raise HTTPException(
            status_code=403,
            detail={"error": "tenant_scope_invalid", "audit_event_id": event_id},
        )
    if any(_path_is_within_prefix(path, prefix) for prefix in ADMIN_ONLY_PREFIXES) and role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_role_required", "audit_event_id": event_id},
        )

    return APIContext(user_role=role, tenant_id=tenant_id, audit_event_id=event_id)


class AuditHeaderMiddleware(BaseHTTPMiddleware):
    """Emit one server-generated audit identifier on every API response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        audit_event_id = str(uuid.uuid4())
        request.state.mfll_audit_event_id = audit_event_id
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
    """Attach non-overridable safety fields to deterministic endpoint responses."""

    payload["review_required"] = True
    payload["rbac"] = rbac_envelope()
    payload["audit_event"] = audit_event(endpoint, action)
    return payload


__all__ = [
    "APIContext",
    "AuditHeaderMiddleware",
    "PUBLIC_ENDPOINTS",
    "SessionCapability",
    "audit_event",
    "mint_session_capability",
    "rbac_envelope",
    "require_api_role",
    "review_response",
    "strict_json_bool",
    "validate_session_capability",
]
