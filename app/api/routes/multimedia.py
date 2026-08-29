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


@router.post("/hearing-media/media/{media_id}/transcript-corrections", summary="Record an immutable transcript correction proposal")
def correct_transcript_segment(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().correct_transcript_segment, media_id, payload, action="hearing_media_transcript_correction", endpoint="POST /api/hearing-media/media/{media_id}/transcript-corrections")


@router.post("/hearing-media/media/{media_id}/speaker-review", summary="Review speaker labels in a transcript")
def speaker_review(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().speaker_review, media_id, payload, action="hearing_media_speaker_review", endpoint="POST /api/hearing-media/media/{media_id}/speaker-review")


@router.post("/hearing-media/media/{media_id}/keyframe-reviews", summary="Generate encrypted local video keyframes for review")
def generate_keyframes(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().generate_keyframes, media_id, payload, action="hearing_media_keyframe_generation", endpoint="POST /api/hearing-media/media/{media_id}/keyframe-reviews")


@router.post("/hearing-media/media/{media_id}/keyframe-reviews/{review_id}/annotations", summary="Record a source-bound keyframe annotation")
def annotate_keyframe(media_id: str, review_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().annotate_keyframe, media_id, review_id, payload, action="hearing_media_keyframe_annotation", endpoint="POST /api/hearing-media/media/{media_id}/keyframe-reviews/{review_id}/annotations")


@router.get("/hearing-media/media/{media_id}/keyframe-reviews/{review_id}/frames/{frame_id}", summary="Open one encrypted local video keyframe")
def keyframe_preview(media_id: str, review_id: str, frame_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().keyframe_preview, media_id, review_id, frame_id, action="hearing_media_keyframe_preview", endpoint="GET /api/hearing-media/media/{media_id}/keyframe-reviews/{review_id}/frames/{frame_id}")


@router.post("/hearing-media/media/{media_id}/redaction-derivatives", summary="Create an encrypted local media redaction derivative")
def create_media_redaction_derivative(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().create_media_redaction_derivative, media_id, payload, action="hearing_media_redaction_derivative", endpoint="POST /api/hearing-media/media/{media_id}/redaction-derivatives")


@router.get("/hearing-media/media/{media_id}/redaction-derivatives/{derivative_id}", summary="Open one encrypted local media redaction derivative")
def media_redaction_preview(media_id: str, derivative_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().media_redaction_preview, media_id, derivative_id, action="hearing_media_redaction_preview", endpoint="GET /api/hearing-media/media/{media_id}/redaction-derivatives/{derivative_id}")


@router.post("/hearing-media/screenshot-conversations", summary="Reconstruct a source-bound screenshot conversation for review")
def reconstruct_screenshot_conversation(payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().reconstruct_screenshot_conversation, payload, action="hearing_media_screenshot_reconstruction", endpoint="POST /api/hearing-media/screenshot-conversations")


@router.get("/hearing-media/screenshot-conversations", summary="List source-bound screenshot conversation reconstructions")
def screenshot_conversations(request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().screenshot_conversations, action="hearing_media_screenshot_list", endpoint="GET /api/hearing-media/screenshot-conversations")


@router.get("/hearing-media/screenshot-conversations/{conversation_id}/screenshots/{screenshot_id}", summary="Inspect one source-bound screenshot observation")
def screenshot_observation(conversation_id: str, screenshot_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().screenshot_observation, conversation_id, screenshot_id, action="hearing_media_screenshot_source", endpoint="GET /api/hearing-media/screenshot-conversations/{conversation_id}/screenshots/{screenshot_id}")


@router.post("/hearing-media/media/{media_id}/metadata-inspections", summary="Inspect local media and image metadata without authentication claims")
def inspect_media_metadata(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().inspect_media_metadata, media_id, payload, action="hearing_media_metadata_inspection", endpoint="POST /api/hearing-media/media/{media_id}/metadata-inspections")


@router.get("/hearing-media/media/{media_id}/metadata-inspections/{inspection_id}", summary="Inspect one source-bound media metadata receipt")
def media_metadata_inspection(media_id: str, inspection_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().media_metadata_inspection, media_id, inspection_id, action="hearing_media_metadata_source", endpoint="GET /api/hearing-media/media/{media_id}/metadata-inspections/{inspection_id}")


@router.post("/hearing-media/media/{media_id}/courtroom-sessions", summary="Create an offline courtroom-media review session")
def create_courtroom_session(media_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().create_courtroom_session, media_id, payload, action="hearing_media_courtroom_session_create", endpoint="POST /api/hearing-media/media/{media_id}/courtroom-sessions")


@router.get("/hearing-media/courtroom-sessions/{session_id}/source", summary="Inspect a courtroom-media session source binding")
def courtroom_session_source(session_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().courtroom_session_source, session_id, action="hearing_media_courtroom_session_source", endpoint="GET /api/hearing-media/courtroom-sessions/{session_id}/source")


@router.get("/hearing-media/courtroom-sessions/{session_id}/playback", summary="Open bounded offline courtroom-media playback")
def courtroom_playback(session_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().courtroom_playback, session_id, action="hearing_media_courtroom_playback", endpoint="GET /api/hearing-media/courtroom-sessions/{session_id}/playback")


@router.post("/hearing-media/courtroom-sessions/{session_id}/sync", summary="Synchronize a courtroom-media session to transcript segments")
def courtroom_sync(session_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().courtroom_sync, session_id, payload, action="hearing_media_courtroom_sync", endpoint="POST /api/hearing-media/courtroom-sessions/{session_id}/sync")


@router.post("/hearing-media/courtroom-sessions/{session_id}/private-notes", summary="Record a separately encrypted private courtroom-review note")
def courtroom_private_note(session_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().add_courtroom_private_note, session_id, payload, action="hearing_media_courtroom_private_note", endpoint="POST /api/hearing-media/courtroom-sessions/{session_id}/private-notes")


@router.get("/hearing-media/courtroom-sessions/{session_id}/private-notes", summary="Open separately encrypted private courtroom-review notes")
def courtroom_private_notes(session_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    _require_role(x_user_role)
    return _invoke(_store().courtroom_private_notes, session_id, action="hearing_media_courtroom_private_notes", endpoint="GET /api/hearing-media/courtroom-sessions/{session_id}/private-notes")


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
