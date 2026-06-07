from __future__ import annotations

from fastapi import APIRouter, Header

from app.api.security import review_response
from app.services import ConversationAdapter
from legal.evidence.fact_to_evidence_mapper import FactToEvidenceMapper
from legal.evidence.timeline_builder import TimelineBuilder

router = APIRouter(tags=["evidence"])
adapter = ConversationAdapter()


@router.post("/evidence/map", summary="Map facts to evidence")
def evidence_map(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    mappings = FactToEvidenceMapper().map(payload.get("facts", []), payload.get("evidence", []))
    response = adapter.for_evidence_map(
        payload,
        {
            "matter_id": payload.get("matter_id"),
            "evidence_map": mappings,
        },
        audience_hint=x_user_role,
    )
    return review_response("POST /api/evidence/map", "fact_to_evidence_mapping", response)


@router.post("/timeline/build", summary="Build a case timeline")
def build_timeline(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    response = adapter.for_timeline(
        payload,
        {
            "matter_id": payload.get("matter_id"),
            "timeline": TimelineBuilder().build(payload.get("events", [])),
        },
        audience_hint=x_user_role,
    )
    return review_response("POST /api/timeline/build", "timeline_build", response)
