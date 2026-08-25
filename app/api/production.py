"""Single production ASGI surface for the installed desktop.

The repository historically carried two independently useful FastAPI apps:
the shipped local workbench and the modular enterprise API.  This gateway
keeps the stable local routes authoritative where paths overlap and exposes
enterprise-only routes through the same loopback origin.  It also publishes a
machine-readable inventory of what is *actually* reachable in production.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.routing import Match

from app.api.main import app as enterprise_app
from legal.evals.human_grounded import HumanEvalError, HumanEvalLedger
from legal.production.signed_authority_updates import (
    AuthorityUpdateChannel,
    AuthorityUpdateError,
)
from legal.security.local_encryption import vault_security_status
from maine_family_law_llm.api import app as local_app
from maine_family_law_llm.feature_tiers import feature_tier_status
from maine_family_law_llm.production_ui import production_ui_manifest
from maine_family_law_llm.runtime_kernel import DurableJobKernel, get_runtime_kernel
from maine_family_law_llm.version import VERSION


# Specialized workbenches accepted through the local service, canonical API,
# matter-scoped encrypted store, shipped UI, source drill-down, review boundary,
# and focused synthetic acceptance suite. Frozen/package reachability is
# reported separately by the release evidence run.
ACCEPTED_FEATURE_IDS = (
    "slice_21_matter_intake",
    "slice_22_operative_order",
    "slice_23_service_notice_deadlines",
    "slice_24_docket_mrecs",
    "slice_25_discovery_disclosure",
    "slice_26_exhibit_binder",
    "slice_27_witness_statements",
    "slice_28_hearing_preparation",
    "slice_29_appellate_preservation",
    "slice_30_uccjea_review",
    "slice_31_icwa_review",
    "slice_32_guardianship_adoption_probate",
    "slice_33_protection_safety_resources",
    "slice_34_parenting_schedule_logistics",
    "slice_35_mediation_negotiation",
    "slice_36_property_debt_valuation",
    "slice_37_modification_circumstances",
    "slice_38_foaa_requests",
    "slice_39_filing_mrecs_readiness",
    "slice_40_image_evidence",
    "slice_41_email_integrity",
    "slice_42_reviewer_handoff",
    "slice_43_language_access",
    "slice_44_resource_navigator",
    "capability_45_smart_matter_inbox",
    "capability_46_saved_workflow_recipes",
    "capability_47_local_media_transcription",
    "capability_48_calendar_interoperability",
    "capability_49_hardware_optimizer",
    "capability_50_research_pinboard",
    "capability_51_redaction_studio",
    "capability_52_matter_next_actions",
    "capability_53_courtroom_presentation",
    "capability_54_encrypted_automatic_backup",
    "capability_55_native_whisper_transcription",
    "capability_56_ocr_correction_studio",
    "capability_57_universal_communications_importer",
    "capability_58_evidence_relationship_graph",
    "capability_59_local_model_manager",
    "capability_60_court_form_autofill",
    "capability_61_advanced_table_extraction",
    "capability_62_financial_document_intelligence",
    "capability_63_semantic_order_comparison",
    "capability_64_authority_update_center",
    "capability_65_guided_legal_research_builder",
    "capability_66_evidence_annotation_studio",
    "capability_67_local_automation_scheduler",
    "capability_68_secure_reviewer_collaboration",
    "capability_69_matter_template_library",
    "capability_70_conflict_entity_resolver",
    "capability_71_desktop_notification_center",
    "capability_72_courtroom_bundle_exporter",
    "capability_73_voice_drafting_commands",
    "capability_74_extension_sdk_permission_center",
)

EXPERIMENTAL_DISABLED_FEATURE_IDS: tuple[str, ...] = ()
_EXPERIMENTAL_DISABLED_API_PREFIXES: tuple[str, ...] = ()


def _experimental_slices_enabled() -> bool:
    return os.environ.get("MFL_ENABLE_EXPERIMENTAL_SLICES_21_31", "").strip() == "1"


def _disabled_experimental_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _EXPERIMENTAL_DISABLED_API_PREFIXES)


class RuntimeJobRequest(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    matter_id: str = Field(default="local", min_length=1, max_length=200)
    idempotency_key: str = Field(default="", max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class AuthorityInstallRequest(BaseModel):
    bundle_id: str = Field(min_length=3, max_length=100)


def authority_update_channel() -> AuthorityUpdateChannel:
    project_root = Path(os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[2])
    trust_path = Path(
        os.environ.get("MFL_AUTHORITY_TRUST_STORE")
        or project_root / "configs" / "authority_update_trust.json"
    )
    trusted_keys: dict[str, str] = {}
    if trust_path.is_file():
        value = json.loads(trust_path.read_text(encoding="utf-8"))
        trusted_keys = {
            str(key): str(encoded) for key, encoded in dict(value.get("trusted_keys") or {}).items()
        }
    root = Path(
        os.environ.get("MFL_AUTHORITY_UPDATE_ROOT")
        or Path(os.environ.get("LOCALAPPDATA") or Path.home())
        / "MaineFamilyLawLLM"
        / "authority-updates"
    )
    return AuthorityUpdateChannel(root, trusted_keys)


def human_eval_ledger() -> HumanEvalLedger:
    root = Path(
        os.environ.get("MFL_HUMAN_EVAL_ROOT")
        or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "human-evals"
    )
    return HumanEvalLedger(root)


_runtime_kernel: DurableJobKernel | None = None


def runtime_kernel() -> DurableJobKernel:
    global _runtime_kernel
    if _runtime_kernel is None:
        _runtime_kernel = get_runtime_kernel()
    return _runtime_kernel


def _route_pairs(application: FastAPI) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for route in application.routes:
        path = str(getattr(route, "path", "") or "")
        for method in getattr(route, "methods", None) or ():
            if path:
                pairs.add((str(method).upper(), path))
    return pairs


def _full_match(application: FastAPI, scope: dict[str, Any]) -> bool:
    for route in application.routes:
        match, _child_scope = route.matches(scope)
        if match is Match.FULL:
            return True
    return False


def _merge_openapi() -> dict[str, Any]:
    local_schema = local_app.openapi()
    enterprise_schema = enterprise_app.openapi()
    merged = dict(local_schema)
    merged["info"] = {
        "title": "Maine Family Law LLM Production API",
        "version": VERSION,
        "description": (
            "Unified installed-desktop API; local routes remain authoritative on overlap."
        ),
    }
    paths = dict(local_schema.get("paths") or {})
    for path, operations in (enterprise_schema.get("paths") or {}).items():
        target = dict(paths.get(path) or {})
        for method, operation in dict(operations).items():
            target.setdefault(method, operation)
        paths[path] = target
    merged["paths"] = paths
    components = dict(local_schema.get("components") or {})
    for group, values in dict(enterprise_schema.get("components") or {}).items():
        target = dict(components.get(group) or {})
        for name, value in dict(values).items():
            target.setdefault(name, value)
        components[group] = target
    merged["components"] = components
    return merged


def capability_inventory() -> dict[str, Any]:
    local_pairs = _route_pairs(local_app)
    enterprise_pairs = _route_pairs(enterprise_app)
    return {
        "schema_version": "production_capability_inventory_v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "version": VERSION,
        "production_entrypoint": "app.api.production:app",
        "routing_policy": "local_authoritative_on_overlap_enterprise_for_unique_routes",
        "local_route_count": len(local_pairs),
        "enterprise_route_count": len(enterprise_pairs),
        "overlap_route_count": len(local_pairs & enterprise_pairs),
        "production_route_count": len(local_pairs | enterprise_pairs),
        "enterprise_only_route_count": len(enterprise_pairs - local_pairs),
        "local_only_route_count": len(local_pairs - enterprise_pairs),
        "ui": {
            "shipped_surface": "src/maine_family_law_llm/ui/workbench.html",
            "shadow_tsx_is_production": False,
            "capability_claim_basis": "reachable_route_inventory",
        },
        "release_scope": {
            "accepted_feature_ids": list(ACCEPTED_FEATURE_IDS),
            "experimental_disabled_feature_ids": list(EXPERIMENTAL_DISABLED_FEATURE_IDS),
            "experimental_backend_override_enabled": False,
            "store_feature_claim_eligible": True,
        },
        "review_required": True,
    }


def _ensure_control_routes() -> None:
    if ("GET", "/api/runtime/capabilities") in _route_pairs(local_app):
        return

    @local_app.get("/api/runtime/capabilities", tags=["runtime"])
    def runtime_capabilities() -> dict[str, Any]:
        return capability_inventory()

    @local_app.get("/api/runtime/kernel/health", tags=["runtime"])
    def runtime_kernel_health() -> dict[str, Any]:
        return runtime_kernel().health()

    @local_app.get("/api/runtime/ui-manifest", tags=["runtime"])
    def runtime_ui_manifest() -> dict[str, Any]:
        return production_ui_manifest()

    @local_app.get("/api/runtime/vault-security", tags=["runtime"])
    def runtime_vault_security() -> dict[str, object]:
        return vault_security_status()

    @local_app.get("/api/runtime/feature-tiers", tags=["runtime"])
    def runtime_feature_tiers() -> dict[str, Any]:
        return feature_tier_status()

    @local_app.get("/api/authority-updates/status", tags=["authority-updates"])
    def authority_updates_status() -> dict[str, Any]:
        return authority_update_channel().status()

    @local_app.post("/api/authority-updates/install", tags=["authority-updates"])
    def authority_updates_install(
        payload: AuthorityInstallRequest,
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> dict[str, Any]:
        if str(x_user_role or "").strip().casefold() != "admin":
            raise HTTPException(status_code=403, detail="admin_role_required")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,99}", payload.bundle_id):
            raise HTTPException(status_code=400, detail="authority_bundle_id_invalid")
        inbox = Path(
            os.environ.get("MFL_AUTHORITY_UPDATE_INBOX")
            or authority_update_channel().root / "inbox"
        ).resolve()
        source = (inbox / payload.bundle_id).resolve()
        if inbox not in source.parents:
            raise HTTPException(status_code=400, detail="authority_bundle_id_invalid")
        try:
            return authority_update_channel().install(source)
        except AuthorityUpdateError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.get("/api/evals/human-grounded/readiness", tags=["evaluations"])
    def human_eval_readiness(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> dict[str, Any]:
        if str(x_user_role or "").strip().casefold() not in {"reviewer", "attorney", "admin"}:
            raise HTTPException(status_code=403, detail="reviewer_role_required")
        return human_eval_ledger().readiness()

    @local_app.post("/api/evals/human-grounded/cases", tags=["evaluations"])
    def human_eval_case_add(
        payload: dict[str, Any],
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> dict[str, Any]:
        if str(x_user_role or "").strip().casefold() != "admin":
            raise HTTPException(status_code=403, detail="admin_role_required")
        try:
            return human_eval_ledger().add_case(payload)
        except HumanEvalError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.post("/api/evals/human-grounded/cases/{case_id}/reviews", tags=["evaluations"])
    def human_eval_review(
        case_id: str,
        payload: dict[str, Any],
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> dict[str, Any]:
        if str(x_user_role or "").strip().casefold() not in {"attorney", "admin"}:
            raise HTTPException(status_code=403, detail="attorney_role_required")
        try:
            return human_eval_ledger().review(case_id, payload)
        except HumanEvalError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.post("/api/evals/human-grounded/cases/{case_id}/adjudicate", tags=["evaluations"])
    def human_eval_adjudicate(
        case_id: str,
        payload: dict[str, Any],
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> dict[str, Any]:
        if str(x_user_role or "").strip().casefold() != "admin":
            raise HTTPException(status_code=403, detail="admin_role_required")
        try:
            return human_eval_ledger().adjudicate(case_id, payload)
        except HumanEvalError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.get("/api/runtime/jobs", tags=["runtime"])
    def runtime_jobs(matter_id: str = "", limit: int = 100) -> dict[str, Any]:
        jobs = runtime_kernel().list_jobs(matter_id=matter_id or None, limit=limit)
        return {"status": "ok", "jobs": jobs, "count": len(jobs)}

    @local_app.post("/api/runtime/jobs", tags=["runtime"])
    def runtime_job_create(payload: RuntimeJobRequest) -> dict[str, Any]:
        return runtime_kernel().create_job(
            payload.job_type,
            payload.payload,
            matter_id=payload.matter_id,
            idempotency_key=payload.idempotency_key or None,
        )

    @local_app.get("/api/runtime/jobs/{job_id}", tags=["runtime"])
    def runtime_job_get(job_id: str) -> dict[str, Any]:
        job = runtime_kernel().get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        return {**job, "events": runtime_kernel().events(job_id)}

    @local_app.post("/api/runtime/jobs/{job_id}/cancel", tags=["runtime"])
    def runtime_job_cancel(job_id: str) -> dict[str, Any]:
        try:
            return runtime_kernel().request_cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job_not_found") from exc

    @local_app.post("/api/runtime/jobs/recover-expired", tags=["runtime"])
    def runtime_jobs_recover() -> dict[str, Any]:
        recovered = runtime_kernel().recover_expired()
        return {"status": "ok", "recovered": recovered, "count": len(recovered)}


class ProductionApplication:
    """Dispatch one loopback origin across the two existing FastAPI apps."""

    def __init__(self) -> None:
        _ensure_control_routes()
        self.local_app = local_app
        self.enterprise_app = enterprise_app
        self.title = "Maine Family Law LLM Production API"
        self.version = VERSION

    @property
    def routes(self) -> list[Any]:
        seen: set[tuple[str, tuple[str, ...]]] = set()
        routes: list[Any] = []
        for route in [*self.local_app.routes, *self.enterprise_app.routes]:
            key = (
                str(getattr(route, "path", "") or ""),
                tuple(sorted(str(item) for item in (getattr(route, "methods", None) or ()))),
            )
            if key in seen:
                continue
            seen.add(key)
            routes.append(route)
        return routes

    def openapi(self) -> dict[str, Any]:
        return _merge_openapi()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = str(scope.get("path") or "")
            if _disabled_experimental_path(path) and not _experimental_slices_enabled():
                response = JSONResponse(
                    status_code=404,
                    content={
                        "detail": "feature_not_in_release_scope",
                        "status": "experimental_disabled",
                        "review_required": True,
                    },
                    headers={
                        "Cache-Control": "no-store",
                        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
                        "Referrer-Policy": "no-referrer",
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "X-MFL-Release-Scope": "experimental-disabled",
                    },
                )
                await response(scope, receive, send)
                return
            enterprise_match = _full_match(self.enterprise_app, scope)
            local_match = _full_match(self.local_app, scope)
            if enterprise_match and not local_match:
                await self.enterprise_app(scope, receive, send)
                return
        await self.local_app(scope, receive, send)


app = ProductionApplication()


__all__: Iterable[str] = (
    "app",
    "ACCEPTED_FEATURE_IDS",
    "capability_inventory",
    "ProductionApplication",
    "runtime_kernel",
)
