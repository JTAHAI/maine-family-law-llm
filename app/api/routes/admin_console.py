from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.governance.admin_console import AdminConsoleReceiptStore, build_admin_console_summary
from legal.governance.role_policy_simulator import RolePolicySimulationError, RolePolicySimulationStore, simulate_role_policy
from legal.governance.separation_of_duties import SeparationOfDutiesError, SeparationOfDutiesReceiptStore, evaluate_separation_of_duties
from legal.governance.signed_policy_pack_lifecycle import SignedPolicyPackError, SignedPolicyPackStore
from legal.governance.legal_hold import LegalHoldError, LegalHoldStore
from legal.governance.retention_policy_engine import RetentionPolicyEngine, RetentionPolicyEngineError
from legal.governance.audit_verification_console import AuditVerificationConsole, AuditVerificationError
from legal.governance.configuration_export import ConfigurationExportError, ConfigurationExportService
from legal.governance.offline_entitlement import OfflineEntitlementError, OfflineEntitlementService
from legal.governance.organization_readiness import OrganizationReadinessDashboard, OrganizationReadinessError
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["admin", "enterprise-administration"])


def _root() -> Path:
    return Path(os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[3])


def _local(request: Request) -> None:
    decision = evaluate_local_request(method=request.method, path=request.url.path, client_host=request.client.host if request.client else None, host_header=request.headers.get("host", ""), origin_header=request.headers.get("origin", ""), sec_fetch_site=request.headers.get("sec-fetch-site", ""), content_length=request.headers.get("content-length", ""))
    if not decision.allowed:
        raise HTTPException(status_code=decision.status_code, detail=decision.code)


def _admin(role: str | None, tenant_id: str | None) -> tuple[str, str]:
    if str(role or "").strip().casefold() != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise HTTPException(status_code=403, detail="tenant_scope_required")
    return "admin", tenant


def _wrap(endpoint: str, action: str, payload: dict) -> dict:
    response = review_response(endpoint, action, payload)
    response["rbac"] = {"enforced": True, "required_role": "admin", "tenant_scoped": True, "mode": "header_contract_replaceable_by_enterprise_auth_provider"}
    return response


@router.get("/admin/console", summary="Fetch the tenant-scoped administration review console")
def admin_console(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    return _wrap("GET /api/admin/console", "admin_console_inspected", build_admin_console_summary(project_root=_root(), tenant_id=tenant))


@router.post("/admin/console/refresh", summary="Record an encrypted tenant-scoped administration review receipt")
def refresh_admin_console(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    summary = build_admin_console_summary(project_root=_root(), tenant_id=tenant)
    try:
        receipt = AdminConsoleReceiptStore().record(summary, tenant_id=tenant)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _wrap("POST /api/admin/console/refresh", "admin_console_refreshed", {**summary, "audit_receipt": receipt})


@router.post("/admin/role-policy-simulations", summary="Simulate fictional role-policy decisions without changing authorization")
def role_policy_simulation(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        simulation = simulate_role_policy(simulation_id=str(payload.get("simulation_id") or ""), fictional_roles=list(payload.get("fictional_roles") or []), permissions=list(payload.get("permissions") or []), tenant_id=tenant)
        receipt = RolePolicySimulationStore().record(simulation, tenant_id=tenant)
    except RolePolicySimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/role-policy-simulations", "role_policy_simulated", {**simulation, "audit_receipt": receipt})


@router.post("/admin/separation-of-duties", summary="Evaluate independent approval references without performing approval actions")
def separation_of_duties(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        evaluation = evaluate_separation_of_duties(review_id=str(payload.get("review_id") or ""), approvals=list(payload.get("approvals") or []), tenant_id=tenant)
        receipt = SeparationOfDutiesReceiptStore().record(evaluation, tenant_id=tenant)
    except SeparationOfDutiesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/separation-of-duties", "separation_of_duties_evaluated", {**evaluation, "audit_receipt": receipt})


def _policy_packs() -> SignedPolicyPackStore:
    return SignedPolicyPackStore(project_root=_root())


def _active_matter_scope() -> str:
    from maine_family_law_llm import api as local_api

    case_root = local_api.active_case_root()
    if case_root is None:
        raise HTTPException(status_code=409, detail="active_matter_required")
    return str(local_api._case_id(Path(case_root)))


def _legal_holds() -> LegalHoldStore:
    return LegalHoldStore()


def _retention() -> RetentionPolicyEngine:
    return RetentionPolicyEngine()


def _audit_verification() -> AuditVerificationConsole:
    return AuditVerificationConsole()


def _configuration_export() -> ConfigurationExportService:
    return ConfigurationExportService(_root())


def _offline_entitlement() -> OfflineEntitlementService:
    return OfflineEntitlementService(project_root=_root())


def _organization_readiness() -> OrganizationReadinessDashboard:
    return OrganizationReadinessDashboard(_root())


@router.post("/admin/policy-packs/draft", summary="Create an encrypted tenant-scoped policy-pack draft")
def signed_policy_pack_draft(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().draft(tenant_id=tenant, pack_id=str(payload.get("pack_id") or ""), version=str(payload.get("version") or ""), controls=payload.get("controls"))
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/draft", "signed_policy_pack_drafted", result)


@router.post("/admin/policy-packs/{pack_id}/validate", summary="Validate a signed policy-pack draft without activation")
def signed_policy_pack_validate(pack_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().validate(tenant_id=tenant, pack_id=pack_id)
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/{pack_id}/validate", "signed_policy_pack_validated", result)


@router.post("/admin/policy-packs/{pack_id}/approve", summary="Verify an externally signed policy-pack approval")
def signed_policy_pack_approve(pack_id: str, payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().approve(tenant_id=tenant, pack_id=pack_id, signature=dict(payload.get("signature") or {}))
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/{pack_id}/approve", "signed_policy_pack_approval_checked", result)


@router.post("/admin/policy-packs/{pack_id}/activate", summary="Activate only a validated externally signed policy pack")
def signed_policy_pack_activate(pack_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().activate(tenant_id=tenant, pack_id=pack_id)
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/{pack_id}/activate", "signed_policy_pack_activation_checked", result)


@router.post("/admin/policy-packs/{pack_id}/expire", summary="Expire a tenant-scoped policy pack")
def signed_policy_pack_expire(pack_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().expire(tenant_id=tenant, pack_id=pack_id)
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/{pack_id}/expire", "signed_policy_pack_expired", result)


@router.post("/admin/policy-packs/{pack_id}/rollback", summary="Roll back a tenant-scoped policy pack state")
def signed_policy_pack_rollback(pack_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().rollback(tenant_id=tenant, pack_id=pack_id)
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/policy-packs/{pack_id}/rollback", "signed_policy_pack_rolled_back", result)


@router.get("/admin/policy-packs/{pack_id}/diff", summary="Inspect a hash-bound policy-pack diff")
def signed_policy_pack_diff(pack_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _policy_packs().diff(tenant_id=tenant, pack_id=pack_id)
    except SignedPolicyPackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("GET /api/admin/policy-packs/{pack_id}/diff", "signed_policy_pack_diff_inspected", result)


@router.get("/admin/legal-holds", summary="List active-matter legal-hold records")
def legal_holds(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _legal_holds().list(tenant_id=tenant, matter_scope=_active_matter_scope())
    except LegalHoldError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("GET /api/admin/legal-holds", "legal_holds_listed", result)


@router.post("/admin/legal-holds", summary="Place an audited legal hold on selected active-matter artifacts")
def place_legal_hold(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _legal_holds().place(tenant_id=tenant, matter_scope=_active_matter_scope(), hold_id=str(payload.get("hold_id") or ""), artifact_ids=list(payload.get("artifact_ids") or []), authority_ref=str(payload.get("authority_ref") or ""))
    except LegalHoldError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/legal-holds", "legal_hold_placed", result)


@router.post("/admin/legal-holds/{hold_id}/release", summary="Release an active-matter legal hold with explicit authority reference")
def release_legal_hold(hold_id: str, payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _legal_holds().release(tenant_id=tenant, matter_scope=_active_matter_scope(), hold_id=hold_id, release_authority_ref=str(payload.get("release_authority_ref") or ""))
    except LegalHoldError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/legal-holds/{hold_id}/release", "legal_hold_released", result)


@router.get("/admin/retention-plans", summary="List active-matter recoverable retention plans")
def retention_plans(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _retention().list(tenant_id=tenant, matter_scope=_active_matter_scope())
    except RetentionPolicyEngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("GET /api/admin/retention-plans", "retention_plans_listed", result)


@router.post("/admin/retention-plans/preview", summary="Preview a hold-aware retention plan without deleting artifacts")
def preview_retention_plan(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _retention().preview(tenant_id=tenant, matter_scope=_active_matter_scope(), plan_id=str(payload.get("plan_id") or ""), artifact_ids=list(payload.get("artifact_ids") or []), policy_ref=str(payload.get("policy_ref") or ""), recovery_window_days=payload.get("recovery_window_days"))
    except (RetentionPolicyEngineError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/retention-plans/preview", "retention_plan_previewed", result)


@router.post("/admin/retention-plans/{plan_id}/apply", summary="Start a recoverable organization-approved retention window")
def apply_retention_plan(plan_id: str, payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _retention().apply(tenant_id=tenant, matter_scope=_active_matter_scope(), plan_id=plan_id, user_confirmed=payload.get("user_confirmed") is True)
    except RetentionPolicyEngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/retention-plans/{plan_id}/apply", "retention_plan_apply_checked", result)


@router.post("/admin/retention-plans/{plan_id}/cancel", summary="Cancel a recoverable retention plan")
def cancel_retention_plan(plan_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _retention().cancel(tenant_id=tenant, matter_scope=_active_matter_scope(), plan_id=plan_id)
    except RetentionPolicyEngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/retention-plans/{plan_id}/cancel", "retention_plan_cancelled", result)


@router.get("/admin/audit-verification", summary="Verify tenant-scoped local governance audit chains")
def audit_verification(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _audit_verification().verify(tenant_id=tenant, matter_scope=_active_matter_scope())
    except AuditVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("GET /api/admin/audit-verification", "audit_verification_inspected", result)


@router.post("/admin/audit-verification/export", summary="Create an encrypted receipt for a scoped local audit report")
def export_audit_verification(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        console = _audit_verification(); report = console.verify(tenant_id=tenant, matter_scope=_active_matter_scope()); result = console.export_scope_report(report, tenant_id=tenant)
    except AuditVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/audit-verification/export", "audit_verification_scope_report_exported", result)


@router.get("/admin/configuration-export", summary="Build a privacy-safe tenant-scoped configuration manifest")
def configuration_export(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    return _wrap("GET /api/admin/configuration-export", "configuration_manifest_built", _configuration_export().build(tenant_id=tenant))


@router.post("/admin/configuration-export/verify", summary="Verify an external signature for the current configuration manifest")
def verify_configuration_export(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _configuration_export().verify_and_receipt(manifest=dict(payload.get("manifest") or {}), tenant_id=tenant, signature=dict(payload.get("signature") or {}))
    except ConfigurationExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/configuration-export/verify", "configuration_manifest_signature_checked", result)


@router.get("/admin/offline-entitlement", summary="Inspect offline entitlement status without network or matter access")
def offline_entitlement_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    return _wrap("GET /api/admin/offline-entitlement", "offline_entitlement_inspected", _offline_entitlement().status(tenant_id=tenant))


@router.post("/admin/offline-entitlement/verify", summary="Verify a separately supplied offline entitlement")
def verify_offline_entitlement(payload: dict, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        result = _offline_entitlement().verify_and_store(tenant_id=tenant, entitlement=dict(payload.get("entitlement") or {}))
    except OfflineEntitlementError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/offline-entitlement/verify", "offline_entitlement_checked", result)


@router.get("/admin/organization-readiness", summary="Inspect separated organization readiness decisions")
def organization_readiness(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    return _wrap("GET /api/admin/organization-readiness", "organization_readiness_inspected", _organization_readiness().build(tenant_id=tenant))


@router.post("/admin/organization-readiness/refresh", summary="Record an encrypted organization readiness refresh receipt")
def refresh_organization_readiness(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role"), x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    _local(request); _role, tenant = _admin(x_user_role, x_tenant_id)
    try:
        dashboard = _organization_readiness(); result = dashboard.receipt(dashboard.build(tenant_id=tenant), tenant_id=tenant)
    except OrganizationReadinessError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _wrap("POST /api/admin/organization-readiness/refresh", "organization_readiness_refreshed", result)
