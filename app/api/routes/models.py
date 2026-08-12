from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.model_orchestration import AdaptiveRuntimePlanner, ModelControlCenter
from legal.security.local_request_firewall import evaluate_local_request
from maine_family_law_llm.runtime_kernel import ACTIVE_STATUSES, get_runtime_kernel

router = APIRouter(tags=["models"])


def _require_role(role: str | None, *, admin_only: bool = False) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
    if admin_only and normalized != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")


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


def _center() -> ModelControlCenter:
    project_root = _project_root()
    model_store_root = os.environ.get("MFL_MODEL_STORE_ROOT") or None
    return ModelControlCenter(
        project_root=project_root,
        role_catalog_path=project_root / "configs" / "maine_model_roles.json",
        admission_policy_path=project_root / "configs" / "maine_model_admission_policy.json",
        registry_seed_path=project_root / "configs" / "maine_model_registry.seed.json",
        store_root=model_store_root,
    )


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {
                "artifact_path",
                "manifest_path",
                "output_path",
                "snapshot_path",
                "source_path",
                "runtime_executable",
            }:
                continue
            if key.endswith("_path"):
                continue
            sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


@router.get("/models", summary="List admitted and candidate models")
def list_models(
    request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    payload = _center().list_models()
    return review_response("GET /api/models", "list_models", _sanitize_payload(payload))


@router.get("/models/{model_id}", summary="Fetch model registry detail")
def get_model(
    model_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    payload = _center().get_model(model_id)
    return review_response("GET /api/models/{model_id}", "get_model", _sanitize_payload(payload))


@router.post("/models/import", summary="Import a model registry record")
def import_model(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().import_model(payload)
    return review_response("POST /api/models/import", "import_model", _sanitize_payload(result))


@router.post("/models/{model_id}/validate", summary="Validate a model registry record")
def validate_model(
    model_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    result = _center().validate_model(model_id)
    return review_response(
        "POST /api/models/{model_id}/validate", "validate_model", _sanitize_payload(result)
    )


@router.post("/models/{model_id}/benchmark", summary="Record a benchmark run")
def benchmark_model(
    model_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().benchmark_model(model_id, payload)
    return review_response(
        "POST /api/models/{model_id}/benchmark", "benchmark_model", _sanitize_payload(result)
    )


@router.post("/models/{model_id}/admit", summary="Admit a model")
def admit_model(
    model_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().admit_model(model_id, payload)
    return review_response(
        "POST /api/models/{model_id}/admit", "admit_model", _sanitize_payload(result)
    )


@router.post("/models/{model_id}/reject", summary="Reject a model")
def reject_model(
    model_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().reject_model(model_id, payload)
    return review_response(
        "POST /api/models/{model_id}/reject", "reject_model", _sanitize_payload(result)
    )


@router.post("/models/{model_id}/quarantine", summary="Quarantine a model")
def quarantine_model(
    model_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().quarantine_model(model_id, payload)
    return review_response(
        "POST /api/models/{model_id}/quarantine", "quarantine_model", _sanitize_payload(result)
    )


@router.get("/models/{model_id}/health", summary="Fetch a model health profile")
def model_health(
    model_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    result = _center().health(model_id)
    return review_response(
        "GET /api/models/{model_id}/health", "model_health", _sanitize_payload(result)
    )


@router.post("/models/{model_id}/cancel", summary="Cancel model work or mark a run cancelled")
def cancel_model(
    model_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role, admin_only=True)
    result = _center().cancel_model(model_id, payload)
    return review_response(
        "POST /api/models/{model_id}/cancel", "cancel_model", _sanitize_payload(result)
    )


@router.get("/hardware/profile", summary="Fetch the local hardware profile")
def hardware_profile(
    request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    payload = _center().refresh_hardware()
    return review_response(
        "GET /api/hardware/profile", "hardware_profile", _sanitize_payload(payload)
    )


@router.post("/models/estimate", summary="Estimate model resource requirements")
def estimate_model(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    result = _center().estimate(payload)
    return review_response("POST /api/models/estimate", "estimate_model", _sanitize_payload(result))


@router.get("/model-routing/status", summary="Fetch safe routing status")
def routing_status(
    request: Request,
    task: str = "draft_review",
    preferred_model_id: str | None = None,
    require_production: bool = False,
    fallback_mode: str = "deterministic",
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    payload = _center().routing_status(
        task=task,
        preferred_model_id=preferred_model_id,
        require_production=require_production,
        fallback_mode=fallback_mode,
    )
    return review_response(
        "GET /api/model-routing/status", "model_routing_status", _sanitize_payload(payload)
    )


@router.post("/model-runtime/plan", summary="Plan hardware-safe local model execution")
def adaptive_runtime_plan(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_role(x_user_role)
    center = _center()
    profile = center.hardware_profile
    active_jobs = sum(
        1
        for job in get_runtime_kernel().list_jobs(limit=500)
        if job.get("job_type") in {"local_model", "local_agent"}
        and job.get("status") in ACTIVE_STATUSES
    )
    plan = AdaptiveRuntimePlanner(profile).plan(
        task=str(payload.get("task") or "general_chat"),
        models=center.registry.list_records(),
        requested_context_tokens=int(payload.get("context_tokens") or 0),
        requested_concurrency=int(payload.get("concurrency") or 1),
        active_model_jobs=active_jobs,
        require_production=bool(payload.get("require_production", False)),
    )
    return review_response(
        "POST /api/model-runtime/plan",
        "adaptive_runtime_plan",
        _sanitize_payload(plan),
    )
