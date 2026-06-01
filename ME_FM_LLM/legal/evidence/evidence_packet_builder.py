from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvidencePacket:
    matter_id: str
    timeline: list[dict[str, Any]]
    evidence_map: list[dict[str, Any]]
    authorities: list[dict[str, Any]]
    missing_record_checklist: list[str]
    warnings: list[str]
    review_required: bool = True
    export_status: str = "review_required"


class EvidencePacketBuilder:
    def build(
        self,
        matter_id,
        timeline,
        evidence_map,
        authorities,
        *,
        missing_record_checklist: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        packet_warnings = list(warnings or [])
        missing = list(missing_record_checklist or [])

        if not timeline:
            packet_warnings.append("timeline_missing")

        if not evidence_map:
            packet_warnings.append("evidence_map_missing")

        unsupported = [item for item in evidence_map if item.get("support_status") == "unsupported"]
        if unsupported:
            packet_warnings.append("unsupported_facts_present")

        return EvidencePacket(
            matter_id=matter_id,
            timeline=timeline,
            evidence_map=evidence_map,
            authorities=authorities,
            missing_record_checklist=sorted(set(missing)),
            warnings=sorted(set(packet_warnings)),
        )
