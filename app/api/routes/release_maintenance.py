from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.security import review_response
from legal.ops.release_pilot_hardening import (
    AttorneySandboxStore,
    MatterBackupRestoreDrill,
    PrivacySafeObservabilityStore,
    ReleaseEvidenceAuditor,
    ReleasePilotHardeningError,
    ReleasePilotHardeningService,
)
from legal.pilot.real_matter_operations import LimitedRealMatterPilotError, LimitedRealMatterPilotOperationsStore
from legal.pilot.sandbox_operations import AttorneySandboxOperationsError, AttorneySandboxOperationsStore
from legal.release.release_candidate_operations import GAReleaseCandidateError, GAReleaseCandidateOperationsStore
from legal.release.shipment_readiness_operations import GAShipmentReadinessError, GAShipmentReadinessStore
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["release", "pilot", "maintenance"])

_ARTIFACT_TTL_SECONDS = 15 * 60
_ARTIFACT_MAX_TOKENS = 128
_TOKEN_RE = re.compile(r"[a-f0-9]{64}")

_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACTS: dict[str, dict[str, Any]] = {}
_REAL_MATTER_PILOT_ARTIFACTS: dict[str, dict[str, Any]] = {}
_GA_RELEASE_CANDIDATE_ARTIFACTS: dict[str, dict[str, Any]] = {}
_GA_SHIPMENT_ARTIFACTS: dict[str, dict[str, Any]] = {}
_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACT_LOCK = threading.RLock()
_REAL_MATTER_PILOT_ARTIFACT_LOCK = threading.RLock()
_GA_RELEASE_CANDIDATE_ARTIFACT_LOCK = threading.RLock()
_GA_SHIPMENT_ARTIFACT_LOCK = threading.RLock()


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


def _require_role(role: str | None) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")


def _project_root() -> Path:
    return Path(os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[3])


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _active_case_root() -> Path | None:
    return _main_api().active_case_root()


def _review(endpoint: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return review_response(endpoint, action, payload)


def _raise_error(exc: ReleasePilotHardeningError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": str(exc)})


def _pilot_service() -> ReleasePilotHardeningService:
    return ReleasePilotHardeningService(_project_root(), _active_case_root())


def _sandbox_store() -> AttorneySandboxStore:
    return AttorneySandboxStore(_project_root())


def _sandbox_operations_store() -> AttorneySandboxOperationsStore:
    return AttorneySandboxOperationsStore(_project_root())


def _real_matter_store() -> LimitedRealMatterPilotOperationsStore:
    return LimitedRealMatterPilotOperationsStore(_project_root())


def _release_candidate_store() -> GAReleaseCandidateOperationsStore:
    return GAReleaseCandidateOperationsStore(_project_root())


def _shipment_store() -> GAShipmentReadinessStore:
    return GAShipmentReadinessStore(_project_root())


def _scope(store: Any) -> str:
    root = getattr(store, "root", None)
    if root is None:
        return ""
    return hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()


def _prune_artifacts(registry: dict[str, dict[str, Any]], lock: threading.RLock) -> None:
    current = float(time.time())
    stale_before = current - _ARTIFACT_TTL_SECONDS
    with lock:
        stale = [token for token, binding in registry.items() if float(binding.get("created_at") or 0) < stale_before]
        for token in stale:
            registry.pop(token, None)
        if len(registry) > _ARTIFACT_MAX_TOKENS:
            overflow = len(registry) - _ARTIFACT_MAX_TOKENS
            oldest = sorted(registry.items(), key=lambda item: float(item[1].get("created_at") or 0))[:overflow]
            for token, _binding in oldest:
                registry.pop(token, None)


def _public_artifacts(
    store: Any,
    result: dict[str, Any],
    *,
    registry: dict[str, dict[str, Any]],
    lock: threading.RLock,
    download_prefix: str,
) -> list[dict[str, Any]]:
    generation_id = str(result.get("generation_id") or "")
    public: list[dict[str, Any]] = []
    _prune_artifacts(registry, lock)
    for artifact in result.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        filename = str(artifact.get("filename") or "")
        sha256 = str(artifact.get("sha256") or "").casefold()
        if not filename or not _TOKEN_RE.fullmatch(sha256):
            continue
        token = secrets.token_hex(32)
        with lock:
            registry[token] = {
                "created_at": time.time(),
                "scope": _scope(store),
                "generation_id": generation_id,
                "filename": filename,
                "sha256": sha256,
            }
        public.append(
            {
                "filename": filename,
                "sha256": sha256,
                "size_bytes": int(artifact.get("size_bytes") or 0),
                "download_url": f"{download_prefix}/{token}",
            }
        )
    return public


def _download_artifact(
    token: str,
    *,
    registry: dict[str, dict[str, Any]],
    lock: threading.RLock,
    detail: str,
    store_factory: Callable[[], Any],
    error_type: type[ReleasePilotHardeningError],
) -> FileResponse:
    token = str(token or "").strip().casefold()
    if not _TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=404, detail=detail)
    _prune_artifacts(registry, lock)
    with lock:
        binding = dict(registry.get(token) or {})
    if not binding:
        raise HTTPException(status_code=404, detail=detail)
    try:
        store = store_factory()
    except error_type:
        raise HTTPException(status_code=404, detail=detail) from None
    if binding.get("scope") != _scope(store):
        raise HTTPException(status_code=404, detail=detail)
    try:
        path, media_type = store.resolve_artifact(
            str(binding.get("generation_id") or ""),
            str(binding.get("filename") or ""),
        )
    except error_type as exc:
        raise _raise_error(exc) from exc
    if hashlib.sha256(path.read_bytes()).hexdigest() != str(binding.get("sha256") or ""):
        raise HTTPException(status_code=409, detail=f"{detail}_hash_mismatch")
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_type,
        content_disposition_type="attachment",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/release-pilot-hardening/status", summary="Fetch the release pilot hardening status")
def release_pilot_hardening_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _pilot_service().status()
    except ReleasePilotHardeningError as exc:
        payload = {"status": "blocked", "blockers": [exc.code]}
    return _review("GET /api/release-pilot-hardening/status", "release_pilot_hardening_status", payload)


@router.post("/release-pilot-hardening/evidence/audit", summary="Audit release evidence")
def release_pilot_hardening_evidence_audit(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    if not bool(payload.get("approved") is True):
        raise HTTPException(status_code=409, detail="release_evidence_audit_approval_required")
    try:
        return _review(
            "POST /api/release-pilot-hardening/evidence/audit",
            "release_pilot_hardening_evidence_audit",
            ReleaseEvidenceAuditor(_project_root()).audit(),
        )
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.post("/release-pilot-hardening/observability/self-test", summary="Run the observability self-test")
def release_pilot_hardening_observability_self_test(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    if not bool(payload.get("approved") is True):
        raise HTTPException(status_code=409, detail="observability_self_test_approval_required")
    case_root = _active_case_root()
    if case_root is None:
        raise HTTPException(status_code=404, detail="active_matter_unavailable")
    try:
        store = PrivacySafeObservabilityStore(case_root)
        record = store.record(
            "self_test",
            metrics={"count": 1, "duration_ms": 0},
            labels={"component": "local_observability", "operation": "self_test", "status": "pass"},
        )
        return _review(
            "POST /api/release-pilot-hardening/observability/self-test",
            "release_pilot_hardening_observability_self_test",
            {"status": "pass", "record": record, "verification": store.verify(), "review_required": True},
        )
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.post("/release-pilot-hardening/backup-restore/drill", summary="Run the backup and restore drill")
def release_pilot_hardening_backup_restore_drill(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    case_root = _active_case_root()
    if case_root is None:
        raise HTTPException(status_code=404, detail="active_matter_unavailable")
    try:
        started = time.perf_counter()
        result = MatterBackupRestoreDrill(case_root, repo_root=_project_root()).run(approved=bool(payload.get("approved") is True))
        PrivacySafeObservabilityStore(case_root).record(
            "backup_restore",
            metrics={"count": 1, "duration_ms": int((time.perf_counter() - started) * 1000), "bytes": int(result.get("total_bytes") or 0)},
            labels={"component": "matter_backup", "operation": "restore_rehearsal", "status": result.get("status") or "blocked"},
        )
        return _review("POST /api/release-pilot-hardening/backup-restore/drill", "release_pilot_hardening_backup_restore_drill", result)
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.post("/release-pilot-hardening/pilot/participants", summary="Register an attorney sandbox participant")
def release_pilot_hardening_pilot_participant(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_store().register_participant(**payload)
        return _review("POST /api/release-pilot-hardening/pilot/participants", "release_pilot_hardening_pilot_participant", result)
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.post("/release-pilot-hardening/pilot/sessions", summary="Start an attorney sandbox session")
def release_pilot_hardening_pilot_session(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_store().start_session(**payload)
        return _review("POST /api/release-pilot-hardening/pilot/sessions", "release_pilot_hardening_pilot_session", result)
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.post("/release-pilot-hardening/pilot/feedback", summary="Record attorney sandbox feedback")
def release_pilot_hardening_pilot_feedback(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_store().add_feedback(**payload)
        return _review("POST /api/release-pilot-hardening/pilot/feedback", "release_pilot_hardening_pilot_feedback", result)
    except ReleasePilotHardeningError as exc:
        raise _raise_error(exc) from exc


@router.get("/release-pilot-hardening/pilot/dashboard", summary="Fetch the attorney sandbox dashboard")
def release_pilot_hardening_pilot_dashboard(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _sandbox_store().dashboard()
    except ReleasePilotHardeningError as exc:
        payload = {"status": "blocked", "blockers": [exc.code]}
    return _review("GET /api/release-pilot-hardening/pilot/dashboard", "release_pilot_hardening_pilot_dashboard", payload)


@router.get("/attorney-sandbox-operations/status", summary="Fetch attorney sandbox operations status")
def attorney_sandbox_operations_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _sandbox_operations_store().status()
    except AttorneySandboxOperationsError as exc:
        payload = {"status": "blocked", "blockers": [exc.code], "real_matter_allowed": False, "pass48_complete": False, "external_launch_evidence_gate_required": True}
    return _review("GET /api/attorney-sandbox-operations/status", "attorney_sandbox_operations_status", payload)


@router.post("/attorney-sandbox-operations/programs", summary="Create an attorney sandbox program")
def attorney_sandbox_operations_program(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().create_program(**payload)
        return _review("POST /api/attorney-sandbox-operations/programs", "attorney_sandbox_operations_program", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/cohorts", summary="Create an attorney sandbox cohort")
def attorney_sandbox_operations_cohort(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().create_cohort(**payload)
        return _review("POST /api/attorney-sandbox-operations/cohorts", "attorney_sandbox_operations_cohort", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/assignments", summary="Create an attorney sandbox assignment")
def attorney_sandbox_operations_assignment(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().create_assignment(**payload)
        return _review("POST /api/attorney-sandbox-operations/assignments", "attorney_sandbox_operations_assignment", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/reviews", summary="Submit an attorney sandbox review")
def attorney_sandbox_operations_review(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().submit_review(**payload)
        return _review("POST /api/attorney-sandbox-operations/reviews", "attorney_sandbox_operations_review", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/sessions/complete", summary="Complete an attorney sandbox session")
def attorney_sandbox_operations_complete(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().complete_session(**payload)
        return _review("POST /api/attorney-sandbox-operations/sessions/complete", "attorney_sandbox_operations_complete", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/feedback/triage", summary="Triage attorney sandbox feedback")
def attorney_sandbox_operations_feedback_triage(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().triage_feedback(**payload)
        return _review("POST /api/attorney-sandbox-operations/feedback/triage", "attorney_sandbox_operations_feedback_triage", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/attestations", summary="Record an attorney sandbox attestation")
def attorney_sandbox_operations_attestation(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().record_external_attestation(**payload)
        return _review("POST /api/attorney-sandbox-operations/attestations", "attorney_sandbox_operations_attestation", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/eval/export", summary="Export attorney sandbox eval candidates")
def attorney_sandbox_operations_eval_export(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _sandbox_operations_store().export_eval_candidates(**payload)
        return _review("POST /api/attorney-sandbox-operations/eval/export", "attorney_sandbox_operations_eval_export", result)
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.post("/attorney-sandbox-operations/evidence/build", summary="Build attorney sandbox evidence")
def attorney_sandbox_operations_evidence_build(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        store = _sandbox_operations_store()
        result = store.build_evidence_packet(**payload)
        return _review(
            "POST /api/attorney-sandbox-operations/evidence/build",
            "attorney_sandbox_operations_evidence_build",
            {**result, "artifacts": _public_artifacts(store, result, registry=_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACTS, lock=_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACT_LOCK, download_prefix="/api/attorney-sandbox-operations/artifacts")},
        )
    except AttorneySandboxOperationsError as exc:
        raise _raise_error(exc) from exc


@router.get("/attorney-sandbox-operations/artifacts/{token}", summary="Download attorney sandbox artifact")
def attorney_sandbox_operations_artifact(token: str):  # type: ignore[no-untyped-def]
    return _download_artifact(
        token,
        registry=_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACTS,
        lock=_ATTORNEY_SANDBOX_OPERATIONS_ARTIFACT_LOCK,
        detail="attorney_sandbox_operations_artifact_not_available",
        store_factory=_sandbox_operations_store,
        error_type=AttorneySandboxOperationsError,
    )


@router.get("/limited-real-matter-pilot/status", summary="Fetch limited real-matter pilot status")
def limited_real_matter_pilot_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _real_matter_store().status()
    except LimitedRealMatterPilotError as exc:
        payload = {
            "status": "blocked",
            "blockers": [exc.code],
            "training_use_allowed": False,
            "human_review_required": True,
            "pass49_complete": False,
            "external_launch_evidence_gate_required": True,
        }
    return _review("GET /api/limited-real-matter-pilot/status", "limited_real_matter_pilot_status", payload)


@router.post("/limited-real-matter-pilot/programs", summary="Create a limited real-matter program")
def limited_real_matter_pilot_program(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().create_program(**payload)
        return _review("POST /api/limited-real-matter-pilot/programs", "limited_real_matter_pilot_program", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/matters", summary="Enroll a limited real-matter matter")
def limited_real_matter_pilot_matter(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().enroll_matter(**payload)
        return _review("POST /api/limited-real-matter-pilot/matters", "limited_real_matter_pilot_matter", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/work-products", summary="Record a real-matter work product")
def limited_real_matter_pilot_work_product(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().record_work_product(**payload)
        return _review("POST /api/limited-real-matter-pilot/work-products", "limited_real_matter_pilot_work_product", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/daily-reviews", summary="Record a daily real-matter review")
def limited_real_matter_pilot_daily_review(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().record_daily_review(**payload)
        return _review("POST /api/limited-real-matter-pilot/daily-reviews", "limited_real_matter_pilot_daily_review", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/exports", summary="Record a real-matter export attempt")
def limited_real_matter_pilot_export(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().record_export_attempt(**payload)
        return _review("POST /api/limited-real-matter-pilot/exports", "limited_real_matter_pilot_export", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/incidents", summary="Record a real-matter incident")
def limited_real_matter_pilot_incident(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().open_incident(**payload)
        return _review("POST /api/limited-real-matter-pilot/incidents", "limited_real_matter_pilot_incident", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/incidents/update", summary="Update a real-matter incident")
def limited_real_matter_pilot_incident_update(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().update_incident(**payload)
        return _review("POST /api/limited-real-matter-pilot/incidents/update", "limited_real_matter_pilot_incident_update", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/signoffs", summary="Record a real-matter signoff")
def limited_real_matter_pilot_signoff(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _real_matter_store().record_signoff(**payload)
        return _review("POST /api/limited-real-matter-pilot/signoffs", "limited_real_matter_pilot_signoff", result)
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.post("/limited-real-matter-pilot/evidence/build", summary="Build limited real-matter evidence")
def limited_real_matter_pilot_evidence_build(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        store = _real_matter_store()
        result = store.build_evidence_packet(**payload)
        return _review(
            "POST /api/limited-real-matter-pilot/evidence/build",
            "limited_real_matter_pilot_evidence_build",
            {**result, "artifacts": _public_artifacts(store, result, registry=_REAL_MATTER_PILOT_ARTIFACTS, lock=_REAL_MATTER_PILOT_ARTIFACT_LOCK, download_prefix="/api/limited-real-matter-pilot/artifacts")},
        )
    except LimitedRealMatterPilotError as exc:
        raise _raise_error(exc) from exc


@router.get("/limited-real-matter-pilot/artifacts/{token}", summary="Download limited real-matter artifact")
def limited_real_matter_pilot_artifact(token: str):  # type: ignore[no-untyped-def]
    return _download_artifact(
        token,
        registry=_REAL_MATTER_PILOT_ARTIFACTS,
        lock=_REAL_MATTER_PILOT_ARTIFACT_LOCK,
        detail="real_matter_pilot_artifact_not_available",
        store_factory=_real_matter_store,
        error_type=LimitedRealMatterPilotError,
    )


@router.get("/ga-release-candidate/status", summary="Fetch GA release candidate status")
def ga_release_candidate_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _release_candidate_store().status()
    except GAReleaseCandidateError as exc:
        payload = {
            "status": "blocked",
            "blockers": [exc.code],
            "release_candidate_frozen": False,
            "pass50_complete": False,
            "external_launch_evidence_gate_required": True,
        }
    return _review("GET /api/ga-release-candidate/status", "ga_release_candidate_status", payload)


@router.post("/ga-release-candidate/candidates", summary="Create a GA release candidate")
def ga_release_candidate_create(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _release_candidate_store().create_candidate(**payload)
        return _review("POST /api/ga-release-candidate/candidates", "ga_release_candidate_create", result)
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-release-candidate/artifacts", summary="Record a GA release candidate artifact")
def ga_release_candidate_artifact_record(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _release_candidate_store().record_artifact(**payload)
        return _review("POST /api/ga-release-candidate/artifacts", "ga_release_candidate_artifact_record", result)
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-release-candidate/signoffs", summary="Record a GA release candidate signoff")
def ga_release_candidate_signoff(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _release_candidate_store().record_signoff(**payload)
        return _review("POST /api/ga-release-candidate/signoffs", "ga_release_candidate_signoff", result)
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-release-candidate/blockers", summary="Record a GA release candidate blocker")
def ga_release_candidate_blocker(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _release_candidate_store().record_blocker(**payload)
        return _review("POST /api/ga-release-candidate/blockers", "ga_release_candidate_blocker", result)
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-release-candidate/freeze", summary="Freeze a GA release candidate")
def ga_release_candidate_freeze(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _release_candidate_store().freeze_candidate(**payload)
        return _review("POST /api/ga-release-candidate/freeze", "ga_release_candidate_freeze", result)
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-release-candidate/evidence/build", summary="Build GA release candidate evidence")
def ga_release_candidate_evidence_build(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        store = _release_candidate_store()
        result = store.build_evidence_packet(**payload)
        return _review(
            "POST /api/ga-release-candidate/evidence/build",
            "ga_release_candidate_evidence_build",
            {**result, "artifacts": _public_artifacts(store, result, registry=_GA_RELEASE_CANDIDATE_ARTIFACTS, lock=_GA_RELEASE_CANDIDATE_ARTIFACT_LOCK, download_prefix="/api/ga-release-candidate/artifacts")},
        )
    except GAReleaseCandidateError as exc:
        raise _raise_error(exc) from exc


@router.get("/ga-release-candidate/artifacts/{token}", summary="Download GA release candidate artifact")
def ga_release_candidate_artifact(token: str):  # type: ignore[no-untyped-def]
    return _download_artifact(
        token,
        registry=_GA_RELEASE_CANDIDATE_ARTIFACTS,
        lock=_GA_RELEASE_CANDIDATE_ARTIFACT_LOCK,
        detail="ga_release_candidate_artifact_not_available",
        store_factory=_release_candidate_store,
        error_type=GAReleaseCandidateError,
    )


@router.get("/ga-shipment-readiness/status", summary="Fetch GA shipment readiness status")
def ga_shipment_readiness_status(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        payload = _shipment_store().status()
    except GAShipmentReadinessError as exc:
        payload = {
            "status": "blocked",
            "blockers": [exc.code],
            "pass51_complete": False,
            "external_shipment_evidence_required": True,
        }
    return _review("GET /api/ga-shipment-readiness/status", "ga_shipment_readiness_status", payload)


@router.post("/ga-shipment-readiness/shipments", summary="Create a GA shipment readiness record")
def ga_shipment_create(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().create_shipment(**payload)
        return _review("POST /api/ga-shipment-readiness/shipments", "ga_shipment_create", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/artifacts", summary="Record a GA shipment artifact")
def ga_shipment_artifact_record(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().record_artifact(**payload)
        return _review("POST /api/ga-shipment-readiness/artifacts", "ga_shipment_artifact_record", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/controls", summary="Record a GA shipment control")
def ga_shipment_control_record(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().record_control(**payload)
        return _review("POST /api/ga-shipment-readiness/controls", "ga_shipment_control_record", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/channels", summary="Record a GA shipment channel")
def ga_shipment_channel_record(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().record_channel(**payload)
        return _review("POST /api/ga-shipment-readiness/channels", "ga_shipment_channel_record", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/blockers", summary="Record a GA shipment blocker")
def ga_shipment_blocker_record(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().record_blocker(**payload)
        return _review("POST /api/ga-shipment-readiness/blockers", "ga_shipment_blocker_record", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/evaluate", summary="Evaluate GA shipment readiness")
def ga_shipment_evaluate(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        result = _shipment_store().evaluate_shipment(**payload)
        return _review("POST /api/ga-shipment-readiness/evaluate", "ga_shipment_evaluate", result)
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.post("/ga-shipment-readiness/evidence/build", summary="Build GA shipment readiness evidence")
def ga_shipment_evidence_build(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    try:
        store = _shipment_store()
        result = store.build_evidence_packet(**payload)
        return _review(
            "POST /api/ga-shipment-readiness/evidence/build",
            "ga_shipment_evidence_build",
            {**result, "artifacts": _public_artifacts(store, result, registry=_GA_SHIPMENT_ARTIFACTS, lock=_GA_SHIPMENT_ARTIFACT_LOCK, download_prefix="/api/ga-shipment-readiness/artifacts")},
        )
    except GAShipmentReadinessError as exc:
        raise _raise_error(exc) from exc


@router.get("/ga-shipment-readiness/artifacts/{token}", summary="Download GA shipment readiness artifact")
def ga_shipment_artifact(token: str):  # type: ignore[no-untyped-def]
    return _download_artifact(
        token,
        registry=_GA_SHIPMENT_ARTIFACTS,
        lock=_GA_SHIPMENT_ARTIFACT_LOCK,
        detail="ga_shipment_artifact_not_available",
        store_factory=_shipment_store,
        error_type=GAShipmentReadinessError,
    )
