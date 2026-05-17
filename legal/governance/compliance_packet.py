from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CompliancePacketReport:
    status: str
    packet_items: list[dict[str, Any]]
    blockers: list[str]
    nist_ai_rmf_mapping: dict[str, Any]
    nist_ai_600_1_mapping: dict[str, Any]
    owasp_llm_mapping: dict[str, Any]
    owner_signoff_slots: dict[str, str]
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "packet_items": self.packet_items,
            "blockers": self.blockers,
            "nist_ai_rmf_mapping": self.nist_ai_rmf_mapping,
            "nist_ai_600_1_mapping": self.nist_ai_600_1_mapping,
            "owasp_llm_mapping": self.owasp_llm_mapping,
            "owner_signoff_slots": self.owner_signoff_slots,
        }


class GovernanceCompliancePacketBuilder:
    """Build the diligence packet inventory for NIST/OWASP/privacy/governance review."""

    def __init__(self, policy_path: str | Path, repo_root: str | Path):
        self.policy_path = Path(policy_path)
        self.repo_root = Path(repo_root)
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))

    def build(self) -> CompliancePacketReport:
        required = list(self.policy.get("packet_required_items", []))
        document_artifacts = dict(self.policy.get("document_artifacts", {}))
        packet_items: list[dict[str, Any]] = []
        blockers: list[str] = []
        for item in required:
            artifact = self._artifact_for(item, document_artifacts)
            exists = self._artifact_exists(artifact)
            packet_items.append(
                {
                    "item": item,
                    "artifact": artifact,
                    "status": "present" if exists else "missing",
                    "requires_owner_signoff_before_ga": item in {
                        "vendor_risk_review",
                        "incident_response_plan",
                        "privacy_impact_assessment",
                        "rollback_sop",
                    },
                }
            )
            if not exists:
                blockers.append(f"missing_packet_item:{item}")
        mappings = [
            self.policy.get("nist_ai_rmf_mapping", {}),
            self.policy.get("nist_ai_600_1_mapping", {}),
            self.policy.get("owasp_llm_mapping", {}),
        ]
        if any(not mapping for mapping in mappings):
            blockers.append("missing_framework_mapping")
        return CompliancePacketReport(
            status="pass" if not blockers else "fail",
            packet_items=packet_items,
            blockers=blockers,
            nist_ai_rmf_mapping=self.policy.get("nist_ai_rmf_mapping", {}),
            nist_ai_600_1_mapping=self.policy.get("nist_ai_600_1_mapping", {}),
            owasp_llm_mapping=self.policy.get("owasp_llm_mapping", {}),
            owner_signoff_slots=dict(self.policy.get("owner_signoff_slots", {})),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _artifact_for(self, item: str, document_artifacts: dict[str, str]) -> str:
        if item in document_artifacts:
            return document_artifacts[item]
        if item == "nist_ai_rmf_mapping":
            return "config:nist_ai_rmf_mapping"
        if item == "nist_ai_600_1_mapping":
            return "config:nist_ai_600_1_mapping"
        if item == "owasp_llm_mapping":
            return "config:owasp_llm_mapping"
        if item == "model_cards":
            return "configs/maine_model_registry.seed.json"
        if item == "data_cards":
            return "configs/maine_enterprise_data_product_policy.json"
        return f"packet:{item}"

    def _artifact_exists(self, artifact: str) -> bool:
        if artifact.startswith("packet:") or artifact.startswith("config:"):
            return True
        path = self.repo_root / artifact
        if "#" in artifact:
            path = self.repo_root / artifact.split("#", 1)[0]
        return path.exists()
