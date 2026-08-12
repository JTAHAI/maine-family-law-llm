from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.governance import GovernanceControlCenterService
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["governance"])


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


def _service() -> GovernanceControlCenterService:
    return GovernanceControlCenterService(
        _project_root(),
        evidence_root=os.environ.get("MFL_GOVERNANCE_EVIDENCE_ROOT") or None,
    )


def _wrap(endpoint: str, action: str, payload: dict) -> dict:
    return review_response(endpoint, action, payload)


def _require_role(role: str | None, *, admin_only: bool = False) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in {"attorney", "reviewer", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
    if admin_only and normalized != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")
    return normalized


@router.get("/governance/controls", summary="Fetch the governance control registry")
def controls(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/controls", "governance_controls", _service().control_registry())


@router.get("/governance/framework-mappings", summary="Fetch framework mappings")
def framework_mappings(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/framework-mappings", "governance_framework_mappings", _service().framework_mappings())


@router.get("/governance/policies", summary="Fetch institutional policies")
def policies(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/policies", "governance_policies", _service().policies())


@router.get("/governance/policy-packs", summary="Fetch policy packs")
def policy_packs(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/policy-packs", "governance_policy_packs", _service().policy_packs())


@router.post("/governance/policy-packs/draft", summary="Draft a policy pack")
def draft_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    request_payload = payload or {}
    result = _service().draft_policy_pack(str(request_payload.get("role") or ""), dict(request_payload.get("overrides") or {}))
    return _wrap("POST /api/governance/policy-packs/draft", "governance_policy_pack_draft", result)


@router.post("/governance/policy-packs/compare", summary="Compare two policy packs")
def compare_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    request_payload = payload or {}
    result = _service().compare_policy_packs(str(request_payload.get("base_pack_id") or ""), str(request_payload.get("target_pack_id") or ""))
    return _wrap("POST /api/governance/policy-packs/compare", "governance_policy_pack_compare", result)


@router.post("/governance/reviews", summary="Review a policy pack")
def review_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    role = _require_role(x_user_role)
    request_payload = payload or {}
    result = _service().review_policy_pack(
        str(request_payload.get("pack_id") or ""),
        reviewer=role,
        decision=str(request_payload.get("decision") or "review"),
        reason=str(request_payload.get("reason") or ""),
        conditions=str(request_payload.get("conditions") or ""),
    )
    return _wrap("POST /api/governance/reviews", "governance_policy_pack_review", result)


@router.post("/governance/activation", summary="Activate a policy pack")
def activate_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    role = _require_role(x_user_role, admin_only=True)
    request_payload = payload or {}
    result = _service().activate_policy_pack(
        str(request_payload.get("pack_id") or ""),
        reviewer=role,
        reason=str(request_payload.get("reason") or ""),
    )
    return _wrap("POST /api/governance/activation", "governance_policy_pack_activate", result)


@router.post("/governance/rollback", summary="Rollback a policy pack")
def rollback_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    role = _require_role(x_user_role, admin_only=True)
    request_payload = payload or {}
    result = _service().rollback_policy_pack(
        str(request_payload.get("pack_id") or ""),
        reviewer=role,
        reason=str(request_payload.get("reason") or ""),
    )
    return _wrap("POST /api/governance/rollback", "governance_policy_pack_rollback", result)


@router.post("/governance/expire", summary="Expire a policy pack")
def expire_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    role = _require_role(x_user_role, admin_only=True)
    request_payload = payload or {}
    result = _service().expire_policy_pack(
        str(request_payload.get("pack_id") or ""),
        reviewer=role,
        reason=str(request_payload.get("reason") or ""),
        expires_at=str(request_payload.get("expires_at") or "") or None,
    )
    return _wrap("POST /api/governance/expire", "governance_policy_pack_expire", result)


@router.post("/governance/supersede", summary="Supersede a policy pack")
def supersede_policy_pack(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    role = _require_role(x_user_role, admin_only=True)
    request_payload = payload or {}
    result = _service().supersede_policy_pack(
        str(request_payload.get("pack_id") or ""),
        reviewer=role,
        reason=str(request_payload.get("reason") or ""),
        new_version=str(request_payload.get("new_version") or ""),
    )
    return _wrap("POST /api/governance/supersede", "governance_policy_pack_supersede", result)


@router.get("/governance/model-cards", summary="Fetch model cards")
def model_cards(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/model-cards", "governance_model_cards", _service().model_cards())


@router.get("/governance/data-cards", summary="Fetch data cards")
def data_cards(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/data-cards", "governance_data_cards", _service().data_cards())


@router.get("/governance/vendor-risks", summary="Fetch vendor risk records")
def vendor_risks(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/vendor-risks", "governance_vendor_risks", _service().vendor_risks())


@router.get("/governance/exceptions", summary="Fetch governance exceptions")
def exceptions(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/exceptions", "governance_exceptions", _service().exceptions())


@router.post("/governance/exceptions", summary="Record a governance exception")
def record_exception(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _service().record_exception(payload or {})
    return _wrap("POST /api/governance/exceptions", "governance_exception_record", result)


@router.get("/governance/sign-offs", summary="Fetch sign-off matrix")
def sign_offs(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/sign-offs", "governance_sign_offs", _service().sign_offs())


@router.post("/governance/sign-offs", summary="Record a sign-off")
def record_sign_off(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    result = _service().record_sign_off(payload or {})
    return _wrap("POST /api/governance/sign-offs", "governance_sign_off_record", result)


@router.get("/governance/diligence-packet", summary="Build the redacted diligence packet")
def diligence_packet(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/diligence-packet", "governance_diligence_packet", _service().diligence_packet())


@router.get("/governance/history", summary="Fetch governance change history")
def history(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _wrap("GET /api/governance/history", "governance_history", _service().history_report())
