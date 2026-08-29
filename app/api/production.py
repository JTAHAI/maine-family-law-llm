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
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.routing import Match

from app.api.main import app as enterprise_app
from app.api.security import audit_event, rbac_envelope
from legal.api_stability import ApiStabilityProgram
from legal.evals.claim_support_metrics import ClaimSupportMetricRunner, REQUIRED_CLAIM_STATUS_LABELS
from legal.evals.citation_quote_metrics import CitationQuoteVerifierMetricRunner, REQUIRED_QUOTE_DECISIONS
from legal.evals.accessibility_bias_metrics import ACCESSIBILITY_BIAS_CATEGORIES, AccessibilityBiasMetricRunner
from legal.evals.human_grounded import HumanEvalError, HumanEvalLedger
from legal.evals.longitudinal_matter_metrics import LONGITUDINAL_SCENARIOS, LongitudinalMatterMetricRunner
from legal.evals.procedural_safety_metrics import PROCEDURAL_SCENARIOS, ProceduralSafetyMetricRunner
from legal.evals.release_metric_eligibility import ReleaseMetricEligibilityGate
from legal.jurisdiction.packs import JurisdictionPackCatalog, JurisdictionPackError, JurisdictionPackSelectionStore
from legal.release.enterprise_ga_closure import (
    EnterpriseDecisionPacket,
    IncidentResponseProgram,
    OrganizationalSignoffGate,
    PackageSbomGate,
    ReleaseReproducibilityGate,
)
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

# These operation families have a legacy local implementation for development
# compatibility, but their enterprise handlers add the installed gateway's
# role/tenant dependency, loopback firewall, idempotency contract, and audit
# header.  The frozen production gateway must never silently prefer the weaker
# duplicate route merely because both apps happen to register the same path.
_ENTERPRISE_AUTHORITATIVE_PREFIXES: tuple[str, ...] = (
    "/api/release-pilot-hardening",
    "/api/attorney-sandbox-operations",
    "/api/limited-real-matter-pilot",
    "/api/ga-release-candidate",
    "/api/ga-shipment-readiness",
)


def _experimental_slices_enabled() -> bool:
    return os.environ.get("MFL_ENABLE_EXPERIMENTAL_SLICES_21_31", "").strip() == "1"


def _disabled_experimental_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _EXPERIMENTAL_DISABLED_API_PREFIXES)


def _enterprise_authoritative_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _ENTERPRISE_AUTHORITATIVE_PREFIXES)


class RuntimeJobRequest(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    matter_id: str = Field(default="local", min_length=1, max_length=200)
    idempotency_key: str = Field(default="", max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class AuthorityInstallRequest(BaseModel):
    bundle_id: str = Field(min_length=3, max_length=100)


class AuthorityArchiveExportRequest(BaseModel):
    bundle_id: str = Field(default="", max_length=100)


class AuthorityArchiveImportRequest(BaseModel):
    archive_filename: str = Field(min_length=1, max_length=160)


_MAX_AUTHORITY_ARCHIVE_UPLOAD_BYTES = 512 * 1024 * 1024


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


def _authority_bundle_operator(
    *,
    role: str | None,
    tenant_id: str | None,
    endpoint: str,
    action: str,
) -> dict[str, Any]:
    normalized_role = str(role or "").strip().casefold()
    normalized_tenant = str(tenant_id or "").strip()
    if normalized_role != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?", normalized_tenant):
        raise HTTPException(status_code=403, detail="tenant_scope_required")
    return {
        "rbac": rbac_envelope(required_role="admin", tenant_scoped=True),
        "audit_event": audit_event(endpoint, action, role=normalized_role, tenant_id=normalized_tenant),
    }


def human_eval_ledger() -> HumanEvalLedger:
    root = Path(
        os.environ.get("MFL_HUMAN_EVAL_ROOT")
        or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "human-evals"
    )
    return HumanEvalLedger(root)


def claim_support_benchmark_paths() -> dict[str, Path | None]:
    """Read external-only benchmark inputs without copying authority into the app.

    This path is intentionally configuration-only.  An unconfigured release
    workstation receives a blocked, actionable response rather than a made-up
    metric, and no user matter is ever a benchmark input.
    """

    value = lambda name: os.environ.get(name, "").strip()
    return {
        "eval_root": Path(value("MFL_CLAIM_SUPPORT_EVAL_ROOT")) if value("MFL_CLAIM_SUPPORT_EVAL_ROOT") else None,
        "source_text_jsonl": Path(value("MFL_CLAIM_SUPPORT_SOURCE_TEXT_JSONL")) if value("MFL_CLAIM_SUPPORT_SOURCE_TEXT_JSONL") else None,
        "parsed_authority_root": Path(value("MFL_CLAIM_SUPPORT_PARSED_AUTHORITY_ROOT")) if value("MFL_CLAIM_SUPPORT_PARSED_AUTHORITY_ROOT") else None,
    }


def quote_benchmark_paths() -> dict[str, Path | None]:
    value = lambda name: os.environ.get(name, "").strip()
    return {
        "eval_root": Path(value("MFL_QUOTE_BENCHMARK_EVAL_ROOT")) if value("MFL_QUOTE_BENCHMARK_EVAL_ROOT") else None,
        "authority_index": Path(value("MFL_QUOTE_BENCHMARK_AUTHORITY_INDEX")) if value("MFL_QUOTE_BENCHMARK_AUTHORITY_INDEX") else None,
        "source_text_jsonl": Path(value("MFL_QUOTE_BENCHMARK_SOURCE_TEXT_JSONL")) if value("MFL_QUOTE_BENCHMARK_SOURCE_TEXT_JSONL") else None,
        "parsed_authority_root": Path(value("MFL_QUOTE_BENCHMARK_PARSED_AUTHORITY_ROOT")) if value("MFL_QUOTE_BENCHMARK_PARSED_AUTHORITY_ROOT") else None,
    }


def procedural_safety_benchmark_root() -> Path | None:
    configured = os.environ.get("MFL_PROCEDURAL_SAFETY_EVAL_ROOT", "").strip()
    return Path(configured) if configured else None


def accessibility_bias_benchmark_root() -> Path | None:
    configured = os.environ.get("MFL_ACCESSIBILITY_BIAS_EVAL_ROOT", "").strip()
    return Path(configured) if configured else None


def longitudinal_matter_benchmark_root() -> Path | None:
    configured = os.environ.get("MFL_LONGITUDINAL_MATTER_EVAL_ROOT", "").strip()
    return Path(configured) if configured else None


def release_metric_eligibility_root() -> Path | None:
    configured = os.environ.get("MFL_RELEASE_METRIC_ELIGIBILITY_ROOT", "").strip()
    return Path(configured) if configured else None


def jurisdiction_pack_root() -> Path | None:
    configured = os.environ.get("MFL_JURISDICTION_PACK_ROOT", "").strip()
    return Path(configured) if configured else None


def api_contract_baseline_root() -> Path | None:
    configured = os.environ.get("MFL_PUBLIC_API_CONTRACT_ROOT", "").strip()
    return Path(configured) if configured else None


def release_closure_evidence_root() -> Path | None:
    configured = os.environ.get("MFL_RELEASE_CLOSURE_EVIDENCE_ROOT", "").strip()
    return Path(configured) if configured else None


def release_closure_package_path() -> Path | None:
    configured = os.environ.get("MFL_RELEASE_CLOSURE_MSIX_PATH", "").strip()
    return Path(configured) if configured else None


def jurisdiction_pack_selection_store() -> JurisdictionPackSelectionStore:
    configured = os.environ.get("MFL_JURISDICTION_PACK_STATE_ROOT", "").strip()
    return JurisdictionPackSelectionStore(Path(configured) if configured else None)


def _claim_benchmark_context(
    *, role: str | None, tenant_id: str | None, endpoint: str, action: str
) -> dict[str, Any]:
    normalized_role = str(role or "").strip().casefold()
    normalized_tenant = str(tenant_id or "").strip()
    if normalized_role not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?", normalized_tenant):
        raise HTTPException(status_code=403, detail="tenant_scope_required")
    return {
        "review_required": True,
        "rbac": rbac_envelope(required_role="attorney_or_reviewer", tenant_scoped=True),
        "audit_event": audit_event(endpoint, action, role=normalized_role, tenant_id=normalized_tenant),
        "matter_scope": "not_applicable_external_non_matter_evaluation",
        "privacy_boundary": "external_gold_and_authority_roots_remain_outside_application_and_package",
    }


def _claim_benchmark_public_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep external-path and row text out of the desktop release-control UI."""

    public = dict(report)
    public.pop("claim_dataset", None)
    public.pop("source_text_basis", None)
    sanitized_findings: list[dict[str, Any]] = []
    for finding in list(public.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        sanitized = dict(finding)
        sanitized.pop("claim", None)
        sanitized_findings.append(sanitized)
    public["findings"] = sanitized_findings
    return public


def _quote_benchmark_public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = dict(report)
    for key in ("citation_dataset", "quote_dataset", "authority_index_path", "source_text_basis"):
        public.pop(key, None)
    sanitized_findings: list[dict[str, Any]] = []
    for finding in list(public.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        sanitized = dict(finding)
        sanitized.pop("citation", None)
        sanitized_findings.append(sanitized)
    public["findings"] = sanitized_findings
    return public


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

    @local_app.post("/api/authority-updates/export", tags=["authority-updates"])
    def authority_updates_export(
        payload: AuthorityArchiveExportRequest,
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _authority_bundle_operator(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/authority-updates/export",
            action="authority_bundle_export",
        )
        try:
            return {**authority_update_channel().export_archive(payload.bundle_id or None), **context}
        except AuthorityUpdateError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.post("/api/authority-updates/import", tags=["authority-updates"])
    def authority_updates_import(
        payload: AuthorityArchiveImportRequest,
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _authority_bundle_operator(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/authority-updates/import",
            action="authority_bundle_import",
        )
        try:
            return {**authority_update_channel().import_archive(payload.archive_filename), **context}
        except AuthorityUpdateError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc

    @local_app.post("/api/authority-updates/import-upload", tags=["authority-updates"])
    async def authority_updates_import_upload(
        bundle: UploadFile = File(...),
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        """Import one explicitly selected signed portable bundle without exposing a file path."""
        context = _authority_bundle_operator(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/authority-updates/import-upload",
            action="authority_bundle_upload_import",
        )
        incoming_name = str(bundle.filename or "")
        if not incoming_name.endswith(".authority-bundle.zip"):
            raise HTTPException(status_code=400, detail="authority_archive_filename_invalid")
        channel = authority_update_channel()
        inbox = channel.root / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        archive_name = f"uploaded-{uuid.uuid4().hex}.authority-bundle.zip"
        temporary = inbox / f".{archive_name}.tmp"
        target = inbox / archive_name
        written = 0
        try:
            with temporary.open("xb") as output:
                while True:
                    block = await bundle.read(1024 * 1024)
                    if not block:
                        break
                    written += len(block)
                    if written > _MAX_AUTHORITY_ARCHIVE_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="authority_archive_upload_too_large")
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            result = channel.import_archive(archive_name)
            result["uploaded_archive_original_filename"] = incoming_name[:160]
            return {**result, **context}
        except AuthorityUpdateError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc
        finally:
            await bundle.close()
            for path in (temporary, target):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass

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

    @local_app.get("/api/evals/claim-support/benchmark", tags=["evaluations"])
    def claim_support_benchmark_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/claim-support/benchmark",
            action="claim_support_benchmark_status",
        )
        paths = claim_support_benchmark_paths()
        configured = bool(paths["eval_root"] and (paths["source_text_jsonl"] or paths["parsed_authority_root"]))
        return {
            "status": "configured" if configured else "blocked",
            "readiness": "claim_support_benchmark_configured" if configured else "claim_support_benchmark_external_inputs_missing",
            "configured_inputs": {
                "external_eval_root": bool(paths["eval_root"]),
                "source_text_jsonl": bool(paths["source_text_jsonl"]),
                "parsed_authority_root": bool(paths["parsed_authority_root"]),
            },
            "required_status_labels": sorted(REQUIRED_CLAIM_STATUS_LABELS),
            "review_required": True,
            "blockers": [] if configured else ["external_claim_gold_or_authority_input_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/claim-support/benchmark", tags=["evaluations"])
    def claim_support_benchmark_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/claim-support/benchmark",
            action="claim_support_benchmark_run",
        )
        paths = claim_support_benchmark_paths()
        if not paths["eval_root"] or not (paths["source_text_jsonl"] or paths["parsed_authority_root"]):
            return {
                "status": "blocked",
                "readiness": "claim_support_benchmark_external_inputs_missing",
                "blockers": ["external_claim_gold_or_authority_input_not_configured"],
                "required_status_labels": sorted(REQUIRED_CLAIM_STATUS_LABELS),
                **context,
            }
        report = ClaimSupportMetricRunner().run(
            eval_root=paths["eval_root"],
            source_text_jsonl=paths["source_text_jsonl"],
            parsed_authority_root=paths["parsed_authority_root"],
            strict_provenance=True,
        ).as_dict()
        return {**_claim_benchmark_public_report(report), **context}

    @local_app.get("/api/evals/quote-verifier/benchmark", tags=["evaluations"])
    def quote_verifier_benchmark_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/quote-verifier/benchmark",
            action="quote_verifier_benchmark_status",
        )
        paths = quote_benchmark_paths()
        configured = bool(paths["eval_root"] and paths["authority_index"] and (paths["source_text_jsonl"] or paths["parsed_authority_root"]))
        return {
            "status": "configured" if configured else "blocked",
            "readiness": "quote_verifier_benchmark_configured" if configured else "quote_verifier_benchmark_external_inputs_missing",
            "configured_inputs": {key: bool(value) for key, value in paths.items()},
            "required_decisions": sorted(REQUIRED_QUOTE_DECISIONS),
            "review_required": True,
            "blockers": [] if configured else ["external_quote_gold_authority_index_or_source_input_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/quote-verifier/benchmark", tags=["evaluations"])
    def quote_verifier_benchmark_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/quote-verifier/benchmark",
            action="quote_verifier_benchmark_run",
        )
        paths = quote_benchmark_paths()
        if not paths["eval_root"] or not paths["authority_index"] or not (paths["source_text_jsonl"] or paths["parsed_authority_root"]):
            return {
                "status": "blocked",
                "readiness": "quote_verifier_benchmark_external_inputs_missing",
                "blockers": ["external_quote_gold_authority_index_or_source_input_not_configured"],
                "required_decisions": sorted(REQUIRED_QUOTE_DECISIONS),
                **context,
            }
        report = CitationQuoteVerifierMetricRunner().run(
            eval_root=paths["eval_root"],
            authority_index_path=paths["authority_index"],
            source_text_jsonl=paths["source_text_jsonl"],
            parsed_authority_root=paths["parsed_authority_root"],
            strict_provenance=True,
        ).as_dict()
        return {**_quote_benchmark_public_report(report), **context}

    @local_app.get("/api/evals/procedural-safety/benchmark", tags=["evaluations"])
    def procedural_safety_benchmark_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/procedural-safety/benchmark",
            action="procedural_safety_benchmark_status",
        )
        root = procedural_safety_benchmark_root()
        return {
            "status": "configured" if root else "blocked",
            "readiness": "procedural_safety_benchmark_configured" if root else "procedural_safety_benchmark_external_input_missing",
            "configured_inputs": {"external_eval_root": bool(root)},
            "required_scenarios": sorted(PROCEDURAL_SCENARIOS),
            "review_required": True,
            "blockers": [] if root else ["external_procedural_safety_gold_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/procedural-safety/benchmark", tags=["evaluations"])
    def procedural_safety_benchmark_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/procedural-safety/benchmark",
            action="procedural_safety_benchmark_run",
        )
        root = procedural_safety_benchmark_root()
        if not root:
            return {
                "status": "blocked",
                "readiness": "procedural_safety_benchmark_external_input_missing",
                "blockers": ["external_procedural_safety_gold_not_configured"],
                "required_scenarios": sorted(PROCEDURAL_SCENARIOS),
                **context,
            }
        report = ProceduralSafetyMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
        # Unlike a production filing result, the benchmark reports only codes
        # and counts. The external scenario payload remains outside the UI.
        report.pop("filing_payload", None)
        return {**report, **context}

    @local_app.get("/api/evals/accessibility-bias/benchmark", tags=["evaluations"])
    def accessibility_bias_benchmark_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/accessibility-bias/benchmark",
            action="accessibility_bias_benchmark_status",
        )
        root = accessibility_bias_benchmark_root()
        return {
            "status": "configured" if root else "blocked",
            "readiness": "accessibility_bias_benchmark_configured" if root else "accessibility_bias_benchmark_external_input_missing",
            "configured_inputs": {"external_eval_root": bool(root)},
            "required_categories": sorted(ACCESSIBILITY_BIAS_CATEGORIES),
            "review_required": True,
            "human_accessibility_review_required": True,
            "blockers": [] if root else ["external_accessibility_bias_gold_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/accessibility-bias/benchmark", tags=["evaluations"])
    def accessibility_bias_benchmark_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/accessibility-bias/benchmark",
            action="accessibility_bias_benchmark_run",
        )
        root = accessibility_bias_benchmark_root()
        if not root:
            return {
                "status": "blocked",
                "readiness": "accessibility_bias_benchmark_external_input_missing",
                "blockers": ["external_accessibility_bias_gold_not_configured"],
                "required_categories": sorted(ACCESSIBILITY_BIAS_CATEGORIES),
                "human_accessibility_review_required": True,
                **context,
            }
        return {**AccessibilityBiasMetricRunner().run(eval_root=root, strict_provenance=True).as_dict(), **context}

    @local_app.get("/api/evals/longitudinal-matter/benchmark", tags=["evaluations"])
    def longitudinal_matter_benchmark_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/longitudinal-matter/benchmark",
            action="longitudinal_matter_benchmark_status",
        )
        root = longitudinal_matter_benchmark_root()
        return {
            "status": "configured" if root else "blocked",
            "readiness": "longitudinal_matter_benchmark_configured" if root else "longitudinal_matter_benchmark_external_input_missing",
            "configured_inputs": {"external_eval_root": bool(root)},
            "required_scenarios": sorted(LONGITUDINAL_SCENARIOS),
            "review_required": True,
            "synthetic_only": True,
            "attorney_reviewed": False,
            "blockers": [] if root else ["external_longitudinal_scenario_manifest_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/longitudinal-matter/benchmark", tags=["evaluations"])
    def longitudinal_matter_benchmark_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/longitudinal-matter/benchmark",
            action="longitudinal_matter_benchmark_run",
        )
        root = longitudinal_matter_benchmark_root()
        if not root:
            return {
                "status": "blocked",
                "readiness": "longitudinal_matter_benchmark_external_input_missing",
                "blockers": ["external_longitudinal_scenario_manifest_not_configured"],
                "required_scenarios": sorted(LONGITUDINAL_SCENARIOS),
                "synthetic_only": True,
                "attorney_reviewed": False,
                **context,
            }
        report = LongitudinalMatterMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
        # The runner only emits scenario names and status codes.  Keeping this
        # defensive scrub makes the route fail closed if a future evaluator
        # accidentally adds a filesystem location or fixture content.
        report.pop("eval_root", None)
        report.pop("fixture_content", None)
        return {**report, **context}

    @local_app.get("/api/evals/release-metric-eligibility", tags=["evaluations"])
    def release_metric_eligibility_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/evals/release-metric-eligibility",
            action="release_metric_eligibility_status",
        )
        root = release_metric_eligibility_root()
        return {
            "status": "configured" if root else "blocked",
            "readiness": "release_metric_eligibility_configured" if root else "release_metric_eligibility_external_input_missing",
            "configured_inputs": {"external_release_metric_evidence_root": bool(root)},
            "review_required": True,
            "enterprise_decision_eligible": False,
            "blockers": [] if root else ["external_release_metric_evidence_root_not_configured"],
            **context,
        }

    @local_app.post("/api/evals/release-metric-eligibility", tags=["evaluations"])
    def release_metric_eligibility_run(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/evals/release-metric-eligibility",
            action="release_metric_eligibility_run",
        )
        root = release_metric_eligibility_root()
        if not root:
            return {
                "status": "blocked",
                "readiness": "release_metric_eligibility_external_input_missing",
                "enterprise_decision_eligible": False,
                "blockers": ["external_release_metric_evidence_root_not_configured"],
                **context,
            }
        report = ReleaseMetricEligibilityGate(project_root=Path(__file__).resolve().parents[2]).run(eval_root=root).as_dict()
        # The evidence gate has no business exposing the location of its external
        # evidence, its reviewer credentials, or its source content to the UI.
        report.pop("eval_root", None)
        report.pop("measurement_path", None)
        return {**report, **context}

    @local_app.get("/api/jurisdiction-packs", tags=["jurisdictions"])
    def jurisdiction_packs_list(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/jurisdiction-packs",
            action="jurisdiction_pack_catalog_inspected",
        )
        root = jurisdiction_pack_root()
        if not root:
            return {
                "status": "blocked",
                "readiness": "jurisdiction_pack_catalog_not_configured",
                "packs": [],
                "blockers": ["external_jurisdiction_pack_root_not_configured"],
                "jurisdiction_decision_prohibited": True,
                **context,
            }
        try:
            packs = [row.as_dict() for row in JurisdictionPackCatalog(root, project_root=Path(__file__).resolve().parents[2]).list_verified()]
        except JurisdictionPackError as exc:
            return {
                "status": "blocked",
                "packs": [],
                "blockers": [str(exc)],
                "jurisdiction_decision_prohibited": True,
                **context,
            }
        return {
            "status": "pass",
            "packs": packs,
            "pack_count": len(packs),
            "review_required": True,
            "jurisdiction_decision_prohibited": True,
            "authority_data_packaged": False,
            **context,
        }

    @local_app.get("/api/jurisdiction-packs/matters/{matter_id}", tags=["jurisdictions"])
    def jurisdiction_pack_matter_status(
        matter_id: str,
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/jurisdiction-packs/matters/{matter_id}",
            action="jurisdiction_pack_matter_selection_inspected",
        )
        try:
            report = jurisdiction_pack_selection_store().status(tenant_id=str(x_tenant_id or ""), matter_id=matter_id)
        except JurisdictionPackError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {**report, **context, "matter_scope": "tenant_scoped_matter_selection"}

    @local_app.post("/api/jurisdiction-packs/{pack_id}/activate", tags=["jurisdictions"])
    def jurisdiction_pack_activate(
        pack_id: str,
        payload: dict[str, Any],
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/jurisdiction-packs/{pack_id}/activate",
            action="jurisdiction_pack_selected_for_matter",
        )
        root = jurisdiction_pack_root()
        if not root:
            raise HTTPException(status_code=409, detail="external_jurisdiction_pack_root_not_configured")
        try:
            pack = JurisdictionPackCatalog(root, project_root=Path(__file__).resolve().parents[2]).get_verified(pack_id)
            report = jurisdiction_pack_selection_store().select(
                tenant_id=str(x_tenant_id or ""),
                matter_id=str(payload.get("matter_id") or ""),
                pack=pack,
                actor_role=str(x_user_role or "").strip().casefold(),
            )
        except JurisdictionPackError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            **report,
            "pack": pack.as_dict(),
            "authority_data_packaged": False,
            **context,
            "matter_scope": "tenant_scoped_matter_selection",
        }

    @local_app.get("/api/api-stability/status", tags=["api-governance"])
    def api_stability_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/api-stability/status",
            action="api_contract_status_inspected",
        )
        snapshot = ApiStabilityProgram(project_root=Path(__file__).resolve().parents[2]).snapshot()
        return {
            "status": "configured" if api_contract_baseline_root() else "blocked",
            "readiness": "public_api_contract_baseline_configured" if api_contract_baseline_root() else "public_api_contract_baseline_required",
            "contract_version": snapshot["contract_version"],
            "contract_sha256": snapshot["contract_sha256"],
            "endpoint_count": len(snapshot["endpoints"]),
            "blockers": [] if api_contract_baseline_root() else ["external_api_contract_baseline_not_configured"],
            **context,
        }

    @local_app.post("/api/api-stability/compare", tags=["api-governance"])
    def api_stability_compare(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/api-stability/compare",
            action="api_contract_baseline_compared",
        )
        report = ApiStabilityProgram(project_root=Path(__file__).resolve().parents[2]).compare(
            baseline_root=api_contract_baseline_root()
        ).as_dict()
        return {**report, **context}

    @local_app.get("/api/release-provenance/status", tags=["release-closure"])
    def release_provenance_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/release-provenance/status",
            action="exact_package_provenance_status_inspected",
        )
        return {
            "status": "configured" if release_closure_package_path() and release_closure_evidence_root() else "blocked",
            "configured_inputs": {
                "exact_msix": bool(release_closure_package_path()),
                "external_release_evidence": bool(release_closure_evidence_root()),
            },
            "readiness": "exact_package_sbom_requires_msix_and_signed_external_vulnerability_evidence",
            "review_required": True,
            "blockers": [] if release_closure_package_path() and release_closure_evidence_root() else ["exact_msix_and_external_release_evidence_required"],
            **context,
        }

    @local_app.post("/api/release-provenance/audit", tags=["release-closure"])
    def release_provenance_audit(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/release-provenance/audit",
            action="exact_package_provenance_audited",
        )
        report = PackageSbomGate(project_root=Path(__file__).resolve().parents[2]).audit(
            package=release_closure_package_path(),
            evidence_root=release_closure_evidence_root(),
        ).as_dict()
        return {**report, **context}

    @local_app.get("/api/release-reproducibility/status", tags=["release-closure"])
    def release_reproducibility_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/release-reproducibility/status",
            action="release_reproducibility_status_inspected",
        )
        return {
            "status": "configured" if release_closure_package_path() and release_closure_evidence_root() else "blocked",
            "readiness": "two_independent_hash_bound_build_runs_and_external_signature_required",
            "configured_inputs": {"exact_msix": bool(release_closure_package_path()), "external_release_evidence": bool(release_closure_evidence_root())},
            "review_required": True,
            "blockers": [] if release_closure_package_path() and release_closure_evidence_root() else ["exact_msix_and_external_reproducibility_evidence_required"],
            **context,
        }

    @local_app.post("/api/release-reproducibility/verify", tags=["release-closure"])
    def release_reproducibility_verify(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/release-reproducibility/verify",
            action="release_reproducibility_verified",
        )
        package_report = PackageSbomGate(project_root=Path(__file__).resolve().parents[2]).audit(
            package=release_closure_package_path(), evidence_root=release_closure_evidence_root()
        )
        report = ReleaseReproducibilityGate(project_root=Path(__file__).resolve().parents[2]).verify(
            evidence_root=release_closure_evidence_root(), package_report=package_report
        ).as_dict()
        return {**report, **context}

    @local_app.get("/api/incident-response/status", tags=["release-closure"])
    def incident_response_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/incident-response/status",
            action="incident_response_program_inspected",
        )
        return {**IncidentResponseProgram().status(), **context}

    @local_app.post("/api/incident-response/tabletop", tags=["release-closure"])
    def incident_response_tabletop(
        payload: dict[str, Any],
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/incident-response/tabletop",
            action="fictional_incident_response_tabletop_run",
        )
        return {**IncidentResponseProgram().tabletop(str(payload.get("scenario_id") or "")), **context}

    @local_app.get("/api/organizational-signoffs/status", tags=["release-closure"])
    def organizational_signoffs_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/organizational-signoffs/status",
            action="organizational_signoff_status_inspected",
        )
        return {
            "status": "configured" if release_closure_evidence_root() else "blocked",
            "readiness": "externally_signed_legal_security_privacy_accessibility_product_operations_and_release_approvals_required",
            "configured_inputs": {"external_release_evidence": bool(release_closure_evidence_root())},
            "review_required": True,
            "blockers": [] if release_closure_evidence_root() else ["external_organizational_signoff_evidence_required"],
            **context,
        }

    @local_app.post("/api/organizational-signoffs/verify", tags=["release-closure"])
    def organizational_signoffs_verify(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/organizational-signoffs/verify",
            action="organizational_signoff_evidence_verified",
        )
        report = OrganizationalSignoffGate(project_root=Path(__file__).resolve().parents[2]).verify(
            evidence_root=release_closure_evidence_root()
        ).as_dict()
        return {**report, **context}

    @local_app.get("/api/enterprise-ga-decision/status", tags=["release-closure"])
    def enterprise_ga_decision_status(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="GET /api/enterprise-ga-decision/status",
            action="enterprise_ga_decision_status_inspected",
        )
        return {
            "status": "configured" if release_closure_evidence_root() else "blocked",
            "readiness": "two_axis_store_and_enterprise_decision_requires_external_evidence_manifest_and_release_authority",
            "configured_inputs": {"external_release_evidence": bool(release_closure_evidence_root())},
            "store_ga_decision": "STORE_GA_NOT_EVALUATED",
            "enterprise_ga_decision": "ENTERPRISE_GA_BLOCKED",
            "review_required": True,
            "blockers": [] if release_closure_evidence_root() else ["external_enterprise_ga_evidence_required"],
            **context,
        }

    @local_app.post("/api/enterprise-ga-decision/assemble", tags=["release-closure"])
    def enterprise_ga_decision_assemble(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    ) -> dict[str, Any]:
        context = _claim_benchmark_context(
            role=x_user_role,
            tenant_id=x_tenant_id,
            endpoint="POST /api/enterprise-ga-decision/assemble",
            action="enterprise_ga_decision_packet_assembled",
        )
        report = EnterpriseDecisionPacket(project_root=Path(__file__).resolve().parents[2]).assemble(
            evidence_root=release_closure_evidence_root()
        ).as_dict()
        return {**report, **context}

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
            if enterprise_match and (not local_match or _enterprise_authoritative_path(path)):
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
