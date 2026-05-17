from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from legal.evidence.fact_to_evidence_mapper import FactToEvidenceMapper
from legal.evidence.timeline_builder import TimelineBuilder

router = APIRouter(tags=["evidence"])


@router.post("/evidence/map", summary="Map facts to evidence")
def evidence_map(payload: dict):
    mappings = FactToEvidenceMapper().map(payload.get("facts", []), payload.get("evidence", []))
    return review_response(
        "POST /api/evidence/map",
        "fact_to_evidence_mapping",
        {
            "matter_id": payload.get("matter_id"),
            "evidence_map": mappings,
        },
    )


@router.post("/timeline/build", summary="Build a case timeline")
def build_timeline(payload: dict):
    return review_response(
        "POST /api/timeline/build",
        "timeline_build",
        {
            "matter_id": payload.get("matter_id"),
            "timeline": TimelineBuilder().build(payload.get("events", [])),
        },
    )