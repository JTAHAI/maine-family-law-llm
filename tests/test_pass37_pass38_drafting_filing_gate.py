from __future__ import annotations

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.drafting.workspace import DraftWorkspaceBuilder


def _authority():
    return {
        "source_id": "statute-19a-1653",
        "citation": "19-A M.R.S. § 1653",
        "title": "Parental rights and responsibilities",
        "jurisdiction": "maine",
        "authority_status": "verified_official_maine",
        "freshness_status": "fresh",
        "score": 1.0,
    }


def _complete_payload():
    return {
        "review_required": True,
        "human_review_complete": True,
        "privacy_review_complete": True,
        "authority_matrix": [_authority()],
        "citation_report": [
            {"citation": "19-A M.R.S. § 1653", "source_id": "statute-19a-1653", "status": "resolved"}
        ],
        "quote_report": [
            {
                "quoted_text": "best interest of the child",
                "source_id": "statute-19a-1653",
                "match_type": "exact",
                "start_offset": 10,
                "end_offset": 36,
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


def test_pass37_workspace_contains_review_sidebars_and_blocks_default_export():
    workspace = DraftWorkspaceBuilder().build(
        template_id="motion",
        issue_type="motion_to_modify",
        facts=[{"fact": "The child moved schools on 01/03/2026."}],
        authorities=[_authority()],
        requested_relief="Modify parental rights after hearing.",
    ).to_dict()

    assert workspace["review_required"] is True
    assert workspace["export_status"] == "blocked"
    assert workspace["sidebars"]["source_cards"][0]["source_id"] == "statute-19a-1653"
    assert workspace["sidebars"]["authority_matrix"][0]["authority_status"] == "verified_official_maine"
    assert workspace["sidebars"]["claim_support"]["unsupported_count"] == 0
    assert workspace["sidebars"]["missing_facts"]["missing_count"] == 1
    assert "citation_report_missing" in workspace["filing_ready_gate"]["blockers"]
    assert "quote_report_missing" in workspace["filing_ready_gate"]["blockers"]


def test_pass38_gate_allows_only_when_all_mandatory_checks_are_proven_and_reviewed():
    result = FilingReadyGate().evaluate(_complete_payload())

    assert result["filing_ready"] is True
    assert result["export_status"] == "allowed"
    assert result["blockers"] == []
    assert result["mandatory_checks"] == {
        "authority_verified": True,
        "citations_resolved": True,
        "quotes_found": True,
        "legal_claims_supported": True,
        "facts_mapped_to_evidence": True,
        "procedure_posture_checked": True,
        "forms_current": True,
        "privacy_review_complete": True,
        "human_review_complete": True,
    }
    assert result["gate_report"]["immutable_report_hash"]


def test_pass38_gate_blocks_unsupported_claim_stale_form_and_attorney_override():
    payload = _complete_payload()
    payload["claim_support_report"] = {
        "claims": [
            {"claim_id": "claim-bad", "claim": "Unsupported legal assertion.", "support_status": "unsupported"}
        ]
    }
    payload["forms_report"] = {"status": "checked", "stale_forms": ["FM-001"], "unknown_forms": []}
    payload["attorney_override"] = {"requested_by": "attorney-1", "reason": "urgent filing"}

    result = FilingReadyGate().evaluate(payload)

    assert result["filing_ready"] is False
    assert result["export_status"] == "blocked_override_logged"
    assert result["attorney_override_logged"] is True
    assert "claim_not_supported:claim-bad" in result["blockers"]
    assert "stale_form:FM-001" in result["blockers"]
    assert result["gate_report"]["attorney_override"]["effect"] == "logged_only_export_remains_blocked_unless_all_gate_checks_pass"
    assert result["blocked_export_explanation"] == result["blockers"]
    assert result["blocker_panel"]["panel_title"] == "Filing gate blockers"
    assert result["blocker_panel"]["immutable_report_hash"] == result["gate_report"]["immutable_report_hash"]


def test_pass38_gate_accepts_workflow_blockers_and_keeps_exact_report_shape():
    payload = _complete_payload()
    payload["workflow_blockers"] = ["review_ledger_unverified", "active_reviewer_assignment_missing"]

    result = FilingReadyGate().evaluate(payload)

    assert result["filing_ready"] is False
    assert "review_ledger_unverified" in result["blockers"]
    assert "active_reviewer_assignment_missing" in result["blockers"]
    assert result["blocker_panel"]["blockers"] == result["blockers"]
