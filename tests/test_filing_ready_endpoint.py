from app.api.routes.review import filing_ready


def _complete_gate_payload() -> dict:
    return {
        "review_required": True,
        "human_review_complete": True,
        "authority_verified": True,
        "citations_resolved": True,
        "quotes_found": True,
        "legal_claims_supported": True,
        "facts_mapped_to_evidence": True,
        "procedure_posture_checked": True,
        "forms_current": True,
        "privacy_review_complete": True,
        "authority_matrix": [
            {
                "source_id": "authority-1",
                "authority_status": "verified_official_maine",
            }
        ],
        "citation_report": [
            {"citation": "19-A M.R.S. § 1653", "status": "resolved"}
        ],
        "quote_report": [
            {
                "source_id": "authority-1",
                "status": "exact",
                "start_offset": 0,
                "end_offset": 12,
            }
        ],
        "claim_support_report": {
            "claims": [{"claim_id": "claim-1", "support_status": "supported"}]
        },
        "fact_to_evidence_map": [
            {
                "fact_id": "fact-1",
                "source_document_id": "record-1",
                "start_offset": 4,
                "end_offset": 18,
                "support_status": "supported",
            }
        ],
        "procedure_posture_report": {"status": "checked", "blockers": []},
        "forms_report": {
            "status": "checked",
            "stale_forms": [],
            "unknown_forms": [],
            "blockers": [],
        },
        "privacy_report": {"status": "checked", "blockers": []},
        "verification_report": {"blockers": []},
    }


def test_public_filing_ready_check_cannot_self_attest_human_review():
    response = filing_ready(_complete_gate_payload(), x_user_role="reviewer")

    assert response["filing_ready"] is False
    assert response["review_required"] is True
    assert response["export_status"] == "blocked"
    assert "authenticated_human_review_record_required" in response["blockers"]
    assert response["client_human_review_claim_ignored"] is True
    assert response["assessment_scope"] == (
        "request_payload_without_authenticated_review_ledger"
    )
