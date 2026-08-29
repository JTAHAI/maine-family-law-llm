from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.security import (
    mint_session_capability,
    require_api_role,
    review_response,
    strict_json_bool,
    validate_session_capability,
)
from legal.security.local_request_firewall import evaluate_local_request
from legal.security.clipboard_controls import ClipboardSafetyPolicy
from legal.security.privacy_safe_diagnostics import (
    PrivacySafeDiagnosticsError,
    build_support_bundle,
    support_bundle_preview,
)
from legal.security.legal_red_team import LegalRedTeamRunner
from legal.security.privacy_fortress import MatterSecurityFortress, MatterSecurityFortressError
from legal.ops.release_pilot_hardening import PrivacySafeObservabilityStore, ReleasePilotHardeningError

router = APIRouter(tags=["security", "privacy"], dependencies=[Depends(require_api_role)])

_SESSION_ACTIONS = {
    "security_privacy_backup",
    "security_privacy_restore",
    "security_privacy_incident_open",
    "security_privacy_incident_close",
    "security_privacy_emergency_revoke",
    "security_privacy_matter_unlock_configure",
    "security_privacy_matter_unlock_verify",
    "security_privacy_matter_unlock_lock",
    "security_privacy_matter_key_enroll_recovery",
    "security_privacy_matter_key_rotate",
    "security_privacy_matter_key_recover_root_wrapping",
    "security_privacy_matter_key_revoke",
    "security_privacy_matter_key_cryptographic_delete",
}


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
        expected_resource_type="matter",
        expected_resource_id=x_matter_id,
    )


def _require_admin_role(x_user_role: str | None) -> None:
    if str(x_user_role or "").strip().casefold() != "admin":
        raise HTTPException(status_code=403, detail={"error": "matter_key_admin_role_required"})


def _support_bundle_inputs(payload: dict) -> dict:
    main_api = _main_api()
    return {
        "sections": payload.get("sections"),
        "client_error_codes": payload.get("client_error_codes"),
        "application_version": str(getattr(main_api, "__version__", "unknown")),
        "local_policy": ClipboardSafetyPolicy().as_dict(),
        "environment": {
            "os_family": platform.system()[:40],
            "python_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
            "frozen_runtime": bool(getattr(sys, "frozen", False)),
        },
    }


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


@router.get("/security/privacy/clipboard-policy", summary="Fetch the no-read local clipboard safety policy")
def clipboard_policy(request: Request):
    _enforce_local_request(request)
    return _wrap(
        "GET /api/security/privacy/clipboard-policy",
        "security_privacy_clipboard_policy",
        ClipboardSafetyPolicy().as_dict(),
    )


@router.get("/security/privacy/matter-key", summary="Inspect non-secret per-matter key hierarchy status")
def matter_key_status(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _enforce_local_request(request)
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    try:
        report = _service().matter_key_status(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
        )
        return _wrap("GET /api/security/privacy/matter-key", "security_privacy_matter_key_status", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/security/privacy/matter-key/{operation}",
    summary="Run a confirmed admin-only per-matter key-hierarchy operation",
)
def manage_matter_key(
    operation: str,
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    _require_admin_role(x_user_role)
    allowed_operations = {
        "enroll_recovery",
        "rotate",
        "recover_root_wrapping",
        "revoke",
        "cryptographic_delete",
    }
    if operation not in allowed_operations:
        raise HTTPException(status_code=404, detail={"error": "matter_key_operation_unavailable"})
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    action = f"security_privacy_matter_key_{operation}"
    _require_session_capability(
        request=request,
        action=action,
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().manage_matter_key(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
            operation=operation,
            recovery_secret=(
                str(request_payload.get("recovery_secret"))
                if request_payload.get("recovery_secret") is not None
                else None
            ),
            approved=strict_json_bool(request_payload, "approved", default=False),
            confirmation=str(request_payload.get("confirmation") or ""),
        )
        return _wrap(
            "POST /api/security/privacy/matter-key/{operation}",
            action,
            report,
        )
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.get("/security/privacy/matter-unlock", summary="Inspect optional local matter-unlock policy")
def matter_unlock_status(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    _enforce_local_request(request)
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    try:
        report = _service().matter_unlock_status(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
        )
        return _wrap("GET /api/security/privacy/matter-unlock", "security_privacy_matter_unlock_status", report)
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/matter-unlock/configure", summary="Configure optional Windows Hello matter unlock")
def configure_matter_unlock(
    request: Request,
    payload: dict | None = None,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_session_token: str | None = Header(default=None, alias="X-MFLL-Session-Token"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    _enforce_local_request(request)
    _require_admin_role(x_user_role)
    request_payload = payload or {}
    main_api = _main_api()
    matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    _require_session_capability(
        request=request,
        action="security_privacy_matter_unlock_configure",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().configure_matter_unlock(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
            enabled=strict_json_bool(request_payload, "enabled", default=False),
            fallback_policy=str(request_payload.get("fallback_policy") or "local_vault_recovery"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap(
            "POST /api/security/privacy/matter-unlock/configure",
            "security_privacy_matter_unlock_configure",
            report,
        )
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/matter-unlock/verify", summary="Request local Windows Hello presence for an enabled matter")
def verify_matter_unlock(
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
        action="security_privacy_matter_unlock_verify",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    try:
        report = _service().verify_matter_unlock(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap(
            "POST /api/security/privacy/matter-unlock/verify",
            "security_privacy_matter_unlock_verify",
            report,
        )
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc


@router.post("/security/privacy/matter-unlock/lock", summary="End the current local matter-unlock session")
def lock_matter_unlock(
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
        action="security_privacy_matter_unlock_lock",
        x_user_role=x_user_role,
        x_tenant_id=x_tenant_id,
        x_matter_id=matter_id,
        x_session_token=x_session_token,
        x_csrf_token=x_csrf_token,
    )
    if not strict_json_bool(request_payload, "approved", default=False):
        raise HTTPException(status_code=409, detail={"error": "matter_unlock_approval_required"})
    try:
        report = _service().lock_matter_unlock(
            matter_id=matter_id,
            tenant_id=str(x_tenant_id or "tenant_unassigned"),
            user_role=str(x_user_role or "viewer"),
        )
        return _wrap(
            "POST /api/security/privacy/matter-unlock/lock",
            "security_privacy_matter_unlock_lock",
            report,
        )
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
    active_matter_id = str((main_api.active_case_root() or Path("active-matter")).name)
    requested_matter_id = str(request_payload.get("matter_id") or active_matter_id)
    if requested_matter_id != active_matter_id:
        raise HTTPException(status_code=403, detail={"error": "session_matter_scope_required"})
    matter_id = active_matter_id
    action = str(request_payload.get("action") or "security_privacy_write")
    if action not in _SESSION_ACTIONS:
        raise HTTPException(status_code=422, detail={"error": "session_action_not_allowlisted"})
    capability = mint_session_capability(
        user_role=str(x_user_role or "viewer"),
        tenant_id=str(x_tenant_id or "tenant_unassigned"),
        matter_id=matter_id,
        action=action,
        resource_type="matter",
        resource_id=matter_id,
        single_use=True,
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


@router.get("/security/privacy/diagnostics/bundle-policy", summary="Describe the privacy-safe support-bundle boundary")
def diagnostics_bundle_policy(request: Request):
    _enforce_local_request(request)
    return _wrap(
        "GET /api/security/privacy/diagnostics/bundle-policy",
        "security_privacy_diagnostics_bundle_policy",
        {
            "status": "pass",
            "allowed_sections": ["product", "security_policy", "local_environment", "client_error_codes"],
            "excluded_categories": ["matter_content", "record_text", "prompts", "names", "paths", "credentials", "raw_logs", "external_urls"],
            "requires_explicit_approval": True,
        },
    )


@router.post("/security/privacy/diagnostics/preview", summary="Preview a redacted local support bundle")
def diagnostics_bundle_preview(request: Request, payload: dict | None = None):
    _enforce_local_request(request)
    try:
        report = support_bundle_preview(**_support_bundle_inputs(payload or {}))
    except PrivacySafeDiagnosticsError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from None
    return _wrap("POST /api/security/privacy/diagnostics/preview", "security_privacy_diagnostics_preview", report)


@router.post("/security/privacy/diagnostics/build", summary="Build an explicit privacy-safe support bundle")
def diagnostics_bundle_build(request: Request, payload: dict | None = None):
    _enforce_local_request(request)
    request_payload = payload or {}
    try:
        report = build_support_bundle(
            approved=strict_json_bool(request_payload, "approved", default=False),
            **_support_bundle_inputs(request_payload),
        )
    except PrivacySafeDiagnosticsError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from None
    return _wrap("POST /api/security/privacy/diagnostics/build", "security_privacy_diagnostics_build", report)


@router.post("/security/privacy/adversarial-corpus/run", summary="Run the local synthetic adversarial safety corpus")
def run_adversarial_corpus(request: Request):
    """Exercise fixed synthetic probes without reading a matter or calling a provider."""

    _enforce_local_request(request)
    try:
        report = LegalRedTeamRunner(project_root=_project_root()).run().as_dict()
    except Exception as exc:
        # The corpus is a release gate: an execution failure must remain visible
        # and fail closed, while the UI receives no host, record, or prompt data.
        raise HTTPException(
            status_code=503,
            detail={"error": "adversarial_corpus_execution_failed", "failure_class": type(exc).__name__},
        ) from None
    return _wrap(
        "POST /api/security/privacy/adversarial-corpus/run",
        "security_privacy_adversarial_corpus_run",
        {
            "status": report["status"],
            "readiness": report["readiness"],
            "review_required": True,
            "local_only": True,
            "synthetic_only": True,
            "no_matter_content_read": True,
            "no_external_request": True,
            "required_categories": report["required_categories"],
            "result_count": len(report["results"]),
            "safe_count": sum(1 for item in report["results"] if item["safe"]),
            "unsafe_case_ids": [item["case_id"] for item in report["results"] if not item["safe"]],
            "no_filing_ready_bypass": report["no_filing_ready_bypass"],
            "blockers": report["blockers"],
        },
    )


@router.get("/security/privacy/telemetry", summary="Inspect the local telemetry preference")
def telemetry_preference_status(request: Request):
    """Expose a content-free, matter-scoped telemetry status only."""

    _enforce_local_request(request)
    try:
        store = PrivacySafeObservabilityStore(_matter_root())
        return _wrap(
            "GET /api/security/privacy/telemetry",
            "security_privacy_telemetry_status",
            {
                "status": "pass",
                "preference": store.preference(),
                "verification": store.verify(),
                "local_only": True,
                "review_required": True,
            },
        )
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc
    except ReleasePilotHardeningError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code}) from exc


@router.post("/security/privacy/telemetry", summary="Set an explicit local-only telemetry preference")
def telemetry_preference_configure(request: Request, payload: dict | None = None):
    """Enable only content-free local metrics after explicit confirmation.

    The preference contains no matter text, paths, identifiers, credentials, or
    remote endpoint. Metrics remain disabled by default and remote exporting is
    not an available mode.
    """

    _enforce_local_request(request)
    _require_json_content_type(request)
    request_payload = payload or {}
    try:
        store = PrivacySafeObservabilityStore(_matter_root())
        preference = store.configure(
            mode=str(request_payload.get("mode") or "off"),
            approved=strict_json_bool(request_payload, "approved", default=False),
        )
        return _wrap(
            "POST /api/security/privacy/telemetry",
            "security_privacy_telemetry_configure",
            {
                "status": "pass",
                "preference": preference,
                "local_only": True,
                "review_required": True,
            },
        )
    except MatterSecurityFortressError as exc:
        raise _handle_error(exc) from exc
    except ReleasePilotHardeningError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code}) from exc


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
