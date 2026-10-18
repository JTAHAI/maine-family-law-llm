from legal.drafting.filing_ready_gate import FilingReadyGate, MANDATORY_CHECKS


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


def test_filing_ready_gate_blocks_export():
    result = FilingReadyGate().evaluate(
        {
            "citations_verified": True,
            "quote_spans_verified": False,
            "human_review_complete": False,
            "authority_verified": True,
        }
    )

    assert result["filing_ready"] is False
    assert result["review_required"] is True
    assert result["export_status"] == "blocked"


def test_summary_booleans_cannot_replace_verifier_evidence():
    result = FilingReadyGate().evaluate({check: True for check in MANDATORY_CHECKS})

    assert result["filing_ready"] is False
    assert result["review_required"] is True
    assert result["export_status"] == "blocked"
    assert {
        "authority_matrix_missing",
        "citation_report_missing",
        "quote_report_missing",
        "claim_support_report_missing",
        "fact_to_evidence_map_missing",
        "procedure_posture_report_missing",
        "forms_freshness_report_missing",
        "privacy_report_missing",
    }.issubset(set(result["blockers"]))


def test_complete_independent_evidence_can_pass_gate():
    result = FilingReadyGate().evaluate(_complete_gate_payload())

    assert result["filing_ready"] is True
    assert result["review_required"] is False
    assert result["export_status"] == "allowed"
    assert result["blockers"] == []
    assert all(result["mandatory_checks"].values())
    assert result["blocker_panel"]["review_required"] is False


def test_explicit_false_summary_vetoes_complete_evidence():
    payload = _complete_gate_payload()
    payload["citations_resolved"] = False

    result = FilingReadyGate().evaluate(payload)

    assert result["filing_ready"] is False
    assert result["mandatory_checks"]["citations_resolved"] is False
    assert "citations_resolved" in result["blockers"]
    assert "citation_report_missing" not in result["blockers"]
