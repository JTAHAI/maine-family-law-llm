from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from legal.evidence.matter_command_center import MatterCommandCenterError, MatterCommandCenterStore

router = APIRouter(tags=["matters"])


def _main_api():
    import maine_family_law_llm.api as main_api

    return main_api


def _store() -> MatterCommandCenterStore:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        raise MatterCommandCenterError("active_matter_unavailable", "The active matter is unavailable.", status_code=409)
    return MatterCommandCenterStore(case_root)


def _records() -> list[dict[str, object]]:
    main_api = _main_api()
    case_root = main_api.active_case_root()
    if case_root is None:
        return []
    return list(main_api.load_case_search_records(case_root))


def _raise_error(exc: MatterCommandCenterError):
    main_api = _main_api()
    raise main_api.HTTPException(status_code=exc.status_code, detail=exc.code) from None


@router.get("/matters/{matter_id}/command-center", summary="Fetch the matter command center")
def get_command_center(matter_id: str):
    try:
        payload = _store().command_center(matter_id, _records())
        return review_response("GET /api/matters/{matter_id}/command-center", "matter_command_center", payload)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.post("/matters/{matter_id}/review-snapshot", summary="Freeze a whole-matter review snapshot")
def review_snapshot(matter_id: str, payload: dict | None = None):
    request = payload or {}
    try:
        snapshot = _store().freeze_snapshot(
            matter_id,
            _records(),
            selected_record_ids=request.get("selected_record_ids") or [],
            variant=str(request.get("variant") or "metadata_only"),
            approved=bool(request.get("approved")),
            note=str(request.get("note") or ""),
        )
        return review_response("POST /api/matters/{matter_id}/review-snapshot", "matter_review_snapshot", snapshot)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.post("/matters/{matter_id}/evidence-packet", summary="Export a whole-matter evidence packet")
def build_evidence_packet(matter_id: str, payload: dict | None = None):
    request = payload or {}
    try:
        result = _store().build_evidence_packet(
            matter_id,
            _records(),
            selected_record_ids=request.get("selected_record_ids") or [],
            snapshot_id=str(request.get("snapshot_id") or ""),
            variant=str(request.get("variant") or "metadata_only"),
            approved=bool(request.get("approved")),
            note=str(request.get("note") or ""),
        )
        return review_response("POST /api/matters/{matter_id}/evidence-packet", "matter_evidence_packet", result)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.get("/matters/{matter_id}/evidence-packet", summary="Fetch the latest whole-matter evidence packet")
def get_evidence_packet(matter_id: str):
    try:
        store = _store()
        command_center = store.command_center(matter_id, _records())
        packet_id = str(command_center.get("latest_packet_id") or "")
        if not packet_id:
            return review_response(
                "GET /api/matters/{matter_id}/evidence-packet",
                "matter_evidence_packet_unavailable",
                {"status": "blocked", "blockers": ["matter_evidence_packet_unavailable"], "review_required": True},
            )
        payload = store.packet(packet_id)
        return review_response("GET /api/matters/{matter_id}/evidence-packet", "matter_evidence_packet_lookup", payload)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.get("/matters/{matter_id}/evidence-packets", summary="List exported evidence packets")
def list_evidence_packets(matter_id: str):
    try:
        payload = _store().list_packets(matter_id)
        return review_response("GET /api/matters/{matter_id}/evidence-packets", "matter_evidence_packet_list", payload)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.get("/evidence-packets/{packet_id}", summary="Fetch an exported evidence packet")
def get_evidence_packet_by_id(packet_id: str):
    try:
        payload = _store().packet(packet_id)
        return review_response("GET /api/evidence-packets/{packet_id}", "matter_evidence_packet_lookup", payload)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.get("/evidence-packets/{packet_id}/receipt", summary="Fetch an evidence packet receipt")
def get_evidence_packet_receipt(packet_id: str):
    try:
        payload = _store().receipt(packet_id)
        return review_response("GET /api/evidence-packets/{packet_id}/receipt", "matter_evidence_packet_receipt", payload)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.post("/evidence-packets/{packet_id}/review", summary="Record a review of an evidence packet")
def review_evidence_packet(packet_id: str, payload: dict | None = None):
    request = payload or {}
    try:
        result = _store().review_packet(
            packet_id,
            reviewer_name=str(request.get("reviewer_name") or ""),
            reviewer_role=str(request.get("reviewer_role") or "other_reviewer"),
            review_status=str(request.get("review_status") or "request_changes"),
            note=str(request.get("note") or ""),
            approved=bool(request.get("approved")),
        )
        return review_response("POST /api/evidence-packets/{packet_id}/review", "matter_evidence_packet_review", result)
    except MatterCommandCenterError as exc:
        _raise_error(exc)


@router.post("/evidence-packets/{packet_id}/compare", summary="Compare two evidence packets")
def compare_evidence_packets(packet_id: str, payload: dict | None = None):
    request = payload or {}
    left_packet_id = str(request.get("left_packet_id") or packet_id)
    right_packet_id = str(request.get("right_packet_id") or "")
    try:
        result = _store().compare_packets(left_packet_id, right_packet_id)
        return review_response("POST /api/evidence-packets/{packet_id}/compare", "matter_evidence_packet_compare", result)
    except MatterCommandCenterError as exc:
        _raise_error(exc)
