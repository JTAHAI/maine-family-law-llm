from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import mint_session_capability, review_response, strict_json_bool, validate_session_capability
from legal.security.local_request_firewall import evaluate_local_request
from legal.security.privacy_fortress import MatterSecurityFortress, MatterSecurityFortressError

router = APIRouter(tags=["security", "privacy"])


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


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


def _matter_root() -> Path:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is not None:
        return Path(case_root)
    configured = os.environ.get("MFL_MATTER_ROOT")
    if configured:
        return Path(configured)
    raise MatterSecurityFortressError("active_matter_unavailable")


def _backup_root() -> Path:
    configured = os.environ.get("MFL_SECURITY_BACKUP_ROOT")
    if configured:
        return Path(configured)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "MaineFamilyLawLLM" / "security"
    return Path(os.environ.get("TMPDIR") or Path.home()) / ".maine-family-law-llm" / "security"


def _service() -> MatterSecurityFortress:
    return MatterSecurityFortress(
        _matter_root(),
        backup_root=_backup_root(),
        project_root=_project_root(),
        encryption_key=os.environ.get("MAINE_MATTER_STORE_KEY"),
        policy_path=_project_root() / "configs" / "maine_llm_injection_defense_policy.json",
    )


def _wrap(endpoint: str, action: str, payload: dict) -> dict:
    return review_response(endpoint, action, payload)


def _handle_error(exc: MatterSecurityFortressError) -> HTTPException:
    return HTTPException(status_code=409, detail={"error": exc.args[0] if exc.args else "security_fortress_error"})


def _require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if request.method not in {"POST", "PUT", "PATCH"}:
        return
    if "application/json" not in content_type.casefold():
        raise HTTPException(status_code=415, detail={"error": "json_content_type_required"})


def _require_session_capability(
    *,
    request: Request,
    action: str,
    x_user_role: str | None,
    x_tenant_id: str | None,
    x_matter_id: str,
    x_session_token: str | None,
    x_csrf_token: str | None,
) -> dict:
    _require_json_content_type(request)
    return validate_session_capability(
        str(x_session_token or ""),
        expected_user_role=str(x_user_role or "viewer"),
        expected_tenant_id=str(x_tenant_id or "tenant_unassigned"),
        expected_matter_id=x_matter_id,
        expected_action=action,
        csrf_token=x_csrf_token,
    )


@router.get("/security/privacy/dashboard", summary="Fetch the security and privacy dashboard")
def dashboard(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _enforce_local_request(request)
    main_api = _main_api()
    try:
        payload = _service().dashboard(
            matter_id=str((main_api.active_case_root() or Path("active-matter")).name),
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
            diagnostics_payload={"request_path": request.url.path, "host": request.headers.get("host", "")},
        )
        return _wrap("GET /api/security/privacy/dashboard", "security_privacy_dashboard", payload)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/session", summary="Mint a short-lived security session capability")
def mint_session(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str(request_payload.get("matter_id") or (main_api.active_case_root() or Path("active-matter")).name)
    action = str(request_payload.get("action") or "security_privacy_write")
    capability = mint_session_capability(
        user_role=str(x_user_role or "viewer"),
        tenant_id=str(x_tenant_id or "tenant_unassigned"),
        matter_id=matter_id,
        action=action,
    )
    return _wrap(
        "POST /api/security/privacy/session",
        "security_privacy_session_mint",
        {"status": "pass", "session": capability.as_dict(), "review_required": True},
    )


@router.post("/security/privacy/backup", summary="Create a hashed matter backup")
def backup(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_backup",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().backup_matter(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        report["user_role"] = str(x_user_role or "viewer")
        return _wrap("POST /api/security/privacy/backup", "security_privacy_backup", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/restore", summary="Verify and rehearse a matter restore")
def restore(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_restore",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().restore_matter(
            backup_id=str(request_payload.get("backup_id") or ""),
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        report["user_role"] = str(x_user_role or "viewer")
        return _wrap("POST /api/security/privacy/restore", "security_privacy_restore", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/injection-scan", summary="Run prompt-injection defense")
def injection_scan(
    request: Request,
    payload: dict | None = None,
):
    _enforce_local_request(request)
    request_payload = payload or {}
    report = _service().injection_defense(
        user_prompt=str(request_payload.get("user_prompt") or ""),
        retrieved_segments=list(request_payload.get("retrieved_segments") or []),
        tool_request=request_payload.get("tool_request"),
        output_text=str(request_payload.get("output_text") or ""),
    )
    return _wrap("POST /api/security/privacy/injection-scan", "security_privacy_injection_scan", report)


@router.post("/security/privacy/diagnostics/redact", summary="Redact diagnostic payloads")
def redact_diagnostics(
    request: Request,
    payload: dict | None = None,
):
    _enforce_local_request(request)
    request_payload = payload or {}
    redacted = _service().redacted_diagnostics(request_payload.get("payload") or request_payload)
    return _wrap(
        "POST /api/security/privacy/diagnostics/redact",
        "security_privacy_redact_diagnostics",
        {"status": "pass", "redacted": redacted, "review_required": True},
    )


@router.post("/security/privacy/retention", summary="Resolve a data-class retention policy")
def retention(
    request: Request,
    payload: dict | None = None,
):
    _enforce_local_request(request)
    request_payload = payload or {}
    data_class = str(request_payload.get("data_class") or "user_provided_confidential_matter_data")
    report = _service().retention_status(data_class)
    return _wrap("POST /api/security/privacy/retention", "security_privacy_retention", report)


@router.get("/security/privacy/audit", summary="Verify the security audit chain")
def audit(
    request: Request,
):
    _enforce_local_request(request)
    report = _service().audit_status()
    return _wrap("GET /api/security/privacy/audit", "security_privacy_audit", report)


@router.post("/security/privacy/incidents/open", summary="Open a security incident")
def incident_open(
    request: Request,
    payload: dict | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_incident_open",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().incident_open(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            severity=str(request_payload.get("severity") or "medium"),
            summary=str(request_payload.get("summary") or ""),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap("POST /api/security/privacy/incidents/open", "security_privacy_incident_open", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/incidents/close", summary="Close a security incident")
def incident_close(
    request: Request,
    payload: dict | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_incident_close",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().incident_close(
            incident_id=str(request_payload.get("incident_id") or ""),
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap("POST /api/security/privacy/incidents/close", "security_privacy_incident_close", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/emergency/revoke", summary="Emergency revoke scoped session and export capabilities")
def emergency_revoke(
    request: Request,
    payload: dict | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_emergency_revoke",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().emergency_revoke(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap("POST /api/security/privacy/emergency/revoke", "security_privacy_emergency_revoke", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc
