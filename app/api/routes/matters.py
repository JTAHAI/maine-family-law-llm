from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from legal.evidence.evidence_packet_builder import EvidencePacketBuilder

router = APIRouter(tags=["matters"])


@router.get("/matters/{matter_id}/evidence-packet", summary="Fetch a review-required evidence packet")
def get_evidence_packet(matter_id: str):
    packet = EvidencePacketBuilder().build(
        matter_id=matter_id,
        timeline=[],
        evidence_map=[],
        authorities=[],
        missing_record_checklist=["external_encrypted_matter_store_not_configured_for_this_demo_endpoint"],
        warnings=["review_required", "no_private_matter_data_loaded_from_source_repo"],
    )
    return review_response(
        "GET /api/matters/{matter_id}/evidence-packet",
        "evidence_packet_lookup",
        packet.__dict__,
    )
