#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.drafting.workspace import DraftWorkspaceBuilder


def _authority() -> dict:
    return {
        "source_id": "statute-19a-1653",
        "citation": "19-A M.R.S. § 1653",
        "title": "Parental rights and responsibilities",
        "jurisdiction": "maine",
        "authority_status": "verified_official_maine",
        "freshness_status": "fresh",
        "score": 1.0,
    }


def _complete_gate_payload() -> dict:
    return {
        "review_required": True,
        "human_review_complete": True,
        "authority_matrix": [_authority()],
        "citation_report": [
            {"citation": "19-A M.R.S. § 1653", "source_id": "statute-19a-1653", "status": "resolved"}
        ],
        "quote_report": [
            {
                "quoted_text": "best interest of the child",
                "source_id": "statute-19a-1653",
                "match_type": "exact",
                "start_offset": 12,
                "end_offset": 38,
            }
        ],
        "claim_support_report": {
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim": "The court must evaluate best interest factors.",
                    "support_status": "supported",
                    "source_id": "statute-19a-1653",
                }
            ]
        },
        "fact_to_evidence_map": [
            {
                "fact_id": "fact-1",
                "fact": "The child moved schools on 01/03/2026.",
                "source_document_id": "doc-1",
                "span": {"start_offset": 0, "end_offset": 40},
                "confidence": 0.91,
            }
        ],
        "procedure_posture_report": {"status": "checked", "procedural_posture": "post_judgment"},
        "forms_report": {"status": "checked", "stale_forms": [], "unknown_forms": []},
    }


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass37_pass38_drafting_filing_gate.json"
    workspace = DraftWorkspaceBuilder().build(
        template_id="motion",
        issue_type="motion_to_modify",
        facts=[{"fact": "The child moved schools on 01/03/2026."}],
        authorities=[_authority()],
        requested_relief="Modify parental rights and responsibilities after hearing.",
    ).to_dict()
    complete_gate = FilingReadyGate().evaluate(_complete_gate_payload())
    override_payload = _complete_gate_payload()
    override_payload["claim_support_report"] = {
        "claims": [
            {"claim_id": "bad-claim", "claim": "Unsupported filing-ready claim.", "support_status": "unsupported"}
        ]
    }
    override_payload["attorney_override"] = {"requested_by": "attorney-1", "reason": "test override logging"}
    blocked_override = FilingReadyGate().evaluate(override_payload)
    evidence = {
        "stage": "pass37_pass38_drafting_workspace_filing_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": {
            "template_id": workspace["draft"]["template_id"],
            "review_required": workspace["review_required"],
            "export_status": workspace["export_status"],
            "source_card_count": len(workspace["sidebars"]["source_cards"]),
            "authority_count": len(workspace["sidebars"]["authority_matrix"]),
            "missing_fact_count": workspace["sidebars"]["missing_facts"]["missing_count"],
            "gate_blockers": workspace["filing_ready_gate"]["blockers"],
        },
        "complete_gate": {
            "filing_ready": complete_gate["filing_ready"],
            "export_status": complete_gate["export_status"],
            "mandatory_checks": complete_gate["mandatory_checks"],
            "immutable_report_hash": complete_gate["gate_report"]["immutable_report_hash"],
        },
        "blocked_override": {
            "filing_ready": blocked_override["filing_ready"],
            "export_status": blocked_override["export_status"],
            "attorney_override_logged": blocked_override["attorney_override_logged"],
            "blockers": blocked_override["blockers"],
        },
        "status": "pass"
        if workspace["review_required"]
        and workspace["export_status"] == "blocked"
        and workspace["sidebars"]["source_cards"]
        and complete_gate["filing_ready"] is True
        and complete_gate["export_status"] == "allowed"
        and blocked_override["filing_ready"] is False
        and blocked_override["export_status"] == "blocked_override_logged"
        else "fail",
    }
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
