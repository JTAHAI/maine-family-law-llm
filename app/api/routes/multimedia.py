from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.multimedia.workbench import HearingMediaWorkbenchError, HearingMediaWorkbenchStore
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["multimedia"])


def _require_role(role: str | None) -> None:
    normalized = (role or "").strip().lower()
    if normalized not in {"reviewer", "attorney", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")


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


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _store() -> HearingMediaWorkbenchStore:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        raise HearingMediaWorkbenchError("active_case_unavailable", "The active case workspace is unavailable.", status_code=409)
    return HearingMediaWorkbenchStore(case_root)


def _handle_error(exc: HearingMediaWorkbenchError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except HearingMediaWorkbenchError as exc:
        raise _handle_error(exc) from exc
    return review_response(endpoint, action, result)


@router.get("/hearing-media", summary="Fetch the hearing multimedia workbench")
def get_hearing_media(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().summary, action="hearing_media_summary", endpoint="GET /api/hearing-media")


@router.get("/hearing-media/media", summary="List imported hearing media")
def list_media(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().summary, action="hearing_media_media_list", endpoint="GET /api/hearing-media/media")


@router.post("/hearing-media/import", summary="Import local hearing media records")
def import_media(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().import_media, payload, action="hearing_media_import", endpoint="POST /api/hearing-media/import")


@router.get("/hearing-media/media/{media_id}", summary="Fetch a hearing media record")
def get_media(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().media, media_id, action="hearing_media_get", endpoint="GET /api/hearing-media/media/{media_id}")


@router.post("/hearing-media/media/{media_id}/transcribe", summary="Create a hearing transcript")
def transcribe_media(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().transcribe_media, media_id, payload, action="hearing_media_transcribe", endpoint="POST /api/hearing-media/media/{media_id}/transcribe")


@router.post("/hearing-media/media/{media_id}/speaker-review", summary="Review speaker labels in a transcript")
def speaker_review(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().speaker_review, media_id, payload, action="hearing_media_speaker_review", endpoint="POST /api/hearing-media/media/{media_id}/speaker-review")


@router.post("/hearing-media/media/{media_id}/timeline/build", summary="Build a hearing timeline")
def build_timeline(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().build_timeline, media_id, action="hearing_media_timeline_build", endpoint="POST /api/hearing-media/media/{media_id}/timeline/build")


@router.post("/hearing-media/media/{media_id}/compare", summary="Compare an official transcript to the derived transcript")
def compare_transcripts(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().compare_transcripts, media_id, payload, action="hearing_media_compare", endpoint="POST /api/hearing-media/media/{media_id}/compare")


@router.get("/hearing-media/media/{media_id}/exhibits", summary="Build exhibit references from the transcript")
def exhibit_references(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().exhibit_references, media_id, action="hearing_media_exhibit_references", endpoint="GET /api/hearing-media/media/{media_id}/exhibits")


@router.get("/hearing-media/media/{media_id}/appellate-record", summary="Fetch the appellate record completeness checklist")
def appellate_record(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().appellate_record_completeness, media_id, action="hearing_media_appellate_record", endpoint="GET /api/hearing-media/media/{media_id}/appellate-record")


@router.post("/hearing-media/media/{media_id}/citations", summary="Record transcript citations")
def record_citations(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().record_citations, media_id, payload, action="hearing_media_citations", endpoint="POST /api/hearing-media/media/{media_id}/citations")


@router.post("/hearing-media/media/{media_id}/privacy-scan", summary="Run a local privacy scan on the transcript")
def privacy_scan(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().privacy_scan, media_id, action="hearing_media_privacy_scan", endpoint="POST /api/hearing-media/media/{media_id}/privacy-scan")


@router.post("/hearing-media/media/{media_id}/redacted-copy", summary="Create a separate redacted transcript derivative")
def redacted_copy(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().redacted_copy, media_id, payload, action="hearing_media_redacted_copy", endpoint="POST /api/hearing-media/media/{media_id}/redacted-copy")


@router.post("/hearing-media/media/{media_id}/cancel", summary="Cancel a hearing transcription workflow")
def cancel_transcription(media_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().cancel_transcription, media_id, action="hearing_media_cancel", endpoint="POST /api/hearing-media/media/{media_id}/cancel")


@router.get("/hearing-media/review-history", summary="Fetch hearing media review history")
def review_history(request: Request, limit: int = 200, offset: int = 0, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().review_history, limit=limit, offset=offset, action="hearing_media_review_history", endpoint="GET /api/hearing-media/review-history")


@router.post("/hearing-media/exports", summary="Export a hearing media review bundle")
def export_bundle(request: Request, payload: dict[str, Any] | None = None, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().export_bundle, payload or {}, action="hearing_media_export", endpoint="POST /api/hearing-media/exports")
