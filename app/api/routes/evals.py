from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.evals import EvalReviewStudio, EvalReviewStudioError, ExternalEvalRootError
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["evals"])


def _studio() -> EvalReviewStudio:
    project_root = os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[3]
    configured = os.environ.get("MFL_EVAL_ROOT") or None
    return EvalReviewStudio(project_root=project_root, eval_root=configured)


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


def _require_eval_role(role: str | None) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")


def _handle_eval_error(exc: Exception) -> None:
    if isinstance(exc, ExternalEvalRootError):
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    if isinstance(exc, EvalReviewStudioError):
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    raise


def _bound_int(value: Any, *, default: int, minimum: int = 1, maximum: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"eval_root", "manifest_path", "output_path", "csv_output_path", "source_url_or_path", "snapshot_path"}:
                continue
            if key.endswith("_path") or key.endswith("_root"):
                continue
            sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


@router.get("/evals/status", summary="Evaluation and review lab status")
def eval_status(
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        payload = _studio().status()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/status", "eval_status", _sanitize_payload(payload))


@router.get("/evals/datasets", summary="List evaluation datasets")
def eval_datasets(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        payload = _studio().datasets()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/datasets", "eval_datasets", _sanitize_payload(payload))


@router.get("/evals/datasets/{dataset_id}", summary="Fetch an evaluation dataset")
def eval_dataset(
    dataset_id: str,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        payload = _studio().dataset_detail(dataset_id)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/datasets/{dataset_id}", "eval_dataset_detail", _sanitize_payload(payload))


@router.post("/evals/queue/build", summary="Build an annotation queue")
def build_queue(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().build_queue(
            manifest_path=payload.get("manifest_path"),
            output_path=payload.get("output_path"),
            max_items_per_task_type=_bound_int(payload.get("max_items_per_task_type"), default=25, minimum=1, maximum=250),
            reviewer_ids=[str(item) for item in payload.get("reviewer_ids", []) if str(item).strip()],
            double_review=bool(payload.get("double_review", True)),
            csv_output_path=payload.get("csv_output_path"),
            dataset_filter=[str(item) for item in payload.get("dataset_filter", []) if str(item).strip()],
            source_class_filter=[str(item) for item in payload.get("source_class_filter", []) if str(item).strip()],
            issue_filter=[str(item) for item in payload.get("issue_filter", []) if str(item).strip()],
            posture_filter=[str(item) for item in payload.get("posture_filter", []) if str(item).strip()],
            target_dataset_type=payload.get("target_dataset_type"),
            seed=payload.get("seed"),
            dry_run=bool(payload.get("dry_run", False)),
            include_fixture_candidates=bool(payload.get("include_fixture_candidates", False)),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/queue/build", "build_eval_queue", _sanitize_payload(result))


@router.get("/evals/assignments", summary="List evaluation assignments")
def list_assignments(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        payload = _studio().list_assignments(limit=_bound_int(limit, default=100, minimum=1, maximum=500), offset=max(0, int(offset or 0)))
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/assignments", "list_eval_assignments", _sanitize_payload(payload))


@router.post("/evals/assignments", summary="Build an evaluation assignment bundle")
def build_assignment_bundle(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().build_queue(
            manifest_path=payload.get("manifest_path"),
            output_path=payload.get("output_path"),
            max_items_per_task_type=_bound_int(payload.get("max_items_per_task_type"), default=25, minimum=1, maximum=250),
            reviewer_ids=[str(item) for item in payload.get("reviewer_ids", []) if str(item).strip()],
            double_review=bool(payload.get("double_review", True)),
            csv_output_path=payload.get("csv_output_path"),
            dataset_filter=[str(item) for item in payload.get("dataset_filter", []) if str(item).strip()],
            source_class_filter=[str(item) for item in payload.get("source_class_filter", []) if str(item).strip()],
            issue_filter=[str(item) for item in payload.get("issue_filter", []) if str(item).strip()],
            posture_filter=[str(item) for item in payload.get("posture_filter", []) if str(item).strip()],
            target_dataset_type=payload.get("target_dataset_type"),
            seed=payload.get("seed"),
            dry_run=bool(payload.get("dry_run", False)),
            include_fixture_candidates=bool(payload.get("include_fixture_candidates", False)),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/assignments", "build_eval_assignment_bundle", _sanitize_payload(result))


@router.get("/evals/rows/{row_id}", summary="Fetch a queue row or promoted row")
def get_row(row_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        payload = _studio().get_row(row_id)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/rows/{row_id}", "get_eval_row", _sanitize_payload(payload))


@router.post("/evals/rows/{row_id}/review", summary="Record a first review")
def review_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().review_row(
            row_id,
            reviewer_safe_id=str(payload.get("reviewer_safe_id") or payload.get("reviewer_id") or ""),
            reviewer_role=str(payload.get("reviewer_role") or x_user_role or "reviewer"),
            decision=str(payload.get("decision") or ""),
            confidence=float(payload.get("confidence") or 0.0),
            rationale=str(payload.get("rationale") or payload.get("rationale_summary") or ""),
            blind=bool(payload.get("blind", False)),
            conflict_of_interest_note=str(payload.get("conflict_of_interest_note") or ""),
            comments=str(payload.get("comments") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/review", "eval_row_review", _sanitize_payload(result))


@router.post("/evals/rows/{row_id}/recuse", summary="Record a reviewer recusal")
def recuse_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().record_recusal(
            row_id,
            reviewer_safe_id=str(payload.get("reviewer_safe_id") or payload.get("reviewer_id") or ""),
            reviewer_role=str(payload.get("reviewer_role") or x_user_role or "reviewer"),
            reason=str(payload.get("reason") or payload.get("rationale") or ""),
            conflict_of_interest_note=str(payload.get("conflict_of_interest_note") or ""),
            comments=str(payload.get("comments") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/recuse", "eval_row_recuse", _sanitize_payload(result))


@router.post("/evals/rows/{row_id}/second-review", summary="Record an independent second review")
def second_review_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().second_review_row(
            row_id,
            reviewer_safe_id=str(payload.get("reviewer_safe_id") or payload.get("reviewer_id") or ""),
            reviewer_role=str(payload.get("reviewer_role") or x_user_role or "reviewer"),
            decision=str(payload.get("decision") or ""),
            confidence=float(payload.get("confidence") or 0.0),
            rationale=str(payload.get("rationale") or payload.get("rationale_summary") or ""),
            blind=bool(payload.get("blind", True)),
            conflict_of_interest_note=str(payload.get("conflict_of_interest_note") or ""),
            comments=str(payload.get("comments") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/second-review", "eval_row_second_review", _sanitize_payload(result))


@router.post("/evals/rows/{row_id}/adjudicate", summary="Resolve a review disagreement")
def adjudicate_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().adjudicate_row(
            row_id,
            adjudicator_safe_id=str(payload.get("adjudicator_safe_id") or payload.get("reviewer_safe_id") or ""),
            adjudication_status=str(payload.get("adjudication_status") or "resolved"),
            resolution_label=str(payload.get("resolution_label") or payload.get("decision") or ""),
            rationale=str(payload.get("rationale") or payload.get("rationale_summary") or ""),
            fixed_in_version=str(payload.get("fixed_in_version") or ""),
            supersedes_row_id=payload.get("supersedes_row_id"),
            release_blocker=bool(payload.get("release_blocker", False)),
            owner_status=str(payload.get("owner_status") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/adjudicate", "eval_row_adjudicate", _sanitize_payload(result))


@router.post("/evals/rows/{row_id}/promote", summary="Promote an adjudicated row to gold")
def promote_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().promote_row(
            row_id,
            adjudicator_safe_id=str(payload.get("adjudicator_safe_id") or payload.get("reviewer_safe_id") or x_user_role or ""),
            supersedes_row_id=payload.get("supersedes_row_id"),
            notes=str(payload.get("notes") or payload.get("rationale") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/promote", "eval_row_promote", _sanitize_payload(result))


@router.post("/evals/rows/{row_id}/supersede", summary="Promote a corrected superseding row")
def supersede_row(
    row_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().supersede_row(
            row_id,
            adjudicator_safe_id=str(payload.get("adjudicator_safe_id") or payload.get("reviewer_safe_id") or x_user_role or ""),
            rationale=str(payload.get("rationale") or payload.get("notes") or ""),
            corrected_labels=[str(item) for item in payload.get("corrected_labels", []) if str(item).strip()],
            fixed_in_version=str(payload.get("fixed_in_version") or ""),
            notes=str(payload.get("notes") or ""),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/rows/{row_id}/supersede", "eval_row_supersede", _sanitize_payload(result))


@router.post("/evals/run", summary="Run a regression evaluation")
def run_eval(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().run_eval(
            dataset_id=str(payload.get("dataset_id") or payload.get("dataset") or ""),
            model_id=str(payload.get("model_id") or payload.get("model") or "local-model"),
            index_id=str(payload.get("index_id") or payload.get("index") or ""),
            config_hash=str(payload.get("config_hash") or ""),
            threshold=payload.get("threshold"),
            output_path=payload.get("output_path"),
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/run", "eval_run", _sanitize_payload(result))


@router.post("/evals/runs/{run_id}/cancel", summary="Cancel a regression evaluation")
def cancel_run(
    run_id: str,
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().cancel_run(run_id, reason=str(payload.get("reason") or ""))
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/runs/{run_id}/cancel", "eval_run_cancel", _sanitize_payload(result))


@router.get("/evals/runs/{run_id}", summary="Fetch a regression evaluation run")
def get_run(run_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().get_run(run_id)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/runs/{run_id}", "get_eval_run", _sanitize_payload(result))


@router.get("/evals/metrics", summary="Fetch latest metric evidence")
def get_metrics(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().metrics()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/metrics", "eval_metrics", _sanitize_payload(result))


@router.get("/evals/failures", summary="Fetch failure clusters")
def get_failures(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().failures()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/failures", "eval_failures", _sanitize_payload(result))


@router.get("/evals/release-comparison", summary="Compare the latest run with the accepted release")
def get_release_comparison(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().release_comparison()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/release-comparison", "eval_release_comparison", _sanitize_payload(result))


@router.post("/evals/exports/build", summary="Build the external review export bundle")
def build_exports(
    payload: dict,
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().export_review_bundle(output_dir=payload.get("output_dir") or None)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("POST /api/evals/exports/build", "build_eval_exports", _sanitize_payload(result))


@router.get("/evals/exports/latest", summary="Fetch the latest external review export bundle")
def latest_exports(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_eval_role(x_user_role)
    try:
        result = _studio().export_review_bundle()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        _handle_eval_error(exc)
    return review_response("GET /api/evals/exports/latest", "latest_eval_exports", _sanitize_payload(result))
