"""Fictional false-pass regressions; not legal-quality certification."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers import ClaimSupportVerifier
from test_pass37_pass38_drafting_filing_gate import _complete_payload
from test_v560_authority_verification_workbench import _authority_root


@pytest.mark.parametrize(
    "joiner",
    ["and", "or", "but", "because", "therefore", "although", "unless", "while", "whereas", ";"],
)
def test_source_match_cannot_mask_added_clause(joiner):
    source = "Rule 1 is titled Scope of Rules."
    claim = f"Rule 1 is titled Scope of Rules {joiner} governs actions."
    result = ClaimSupportVerifier().verify(
        claim,
        [source],
        source_ids=["fictional-rule"],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
    )
    assert result["status"] == "partially_supported"
    assert result["supported"] is False
    assert "added clause" in result["message"]
    span = result["best_span"]
    assert span["source_id"] == "fictional-rule"
    assert source[span["start_offset"] : span["end_offset"]] == span["text"]


def test_both_source_bound_clauses_still_supported():
    source = "Rule 1 is titled Scope of Rules and governs actions."
    result = ClaimSupportVerifier().verify(
        source, [source], authority_statuses=["verified_official_maine"]
    )
    assert result["status"] == "supported" and result["supported"] is True


def test_true_source_bound_coordinated_list_still_supported():
    source = "The fictional record lists apples, pears and plums."
    result = ClaimSupportVerifier().verify(source, [source])
    assert result["supported"] is True
    result = ClaimSupportVerifier().verify(
        "The fictional record lists apples, pears and unicorns.", [source]
    )
    assert result["supported"] is False and result["status"] == "partially_supported"


@pytest.mark.parametrize("report_key", ["claim_support_report", "claim_report"])
@pytest.mark.parametrize("summary_key", ["legal_claims_supported", "claims_supported"])
@pytest.mark.parametrize("as_list", [False, True])
def test_gate_rejects_partial_claim_even_with_optimistic_alias(report_key, summary_key, as_list):
    payload = _complete_payload()
    payload.pop("claim_support_report")
    row = {
        "claim_id": "fictional-partial",
        "support_status": "partially_supported",
        "supported": False,
    }
    payload[report_key] = [row] if as_list else {"claims": [row]}
    payload[summary_key] = True
    payload["attorney_override"] = {
        "requested_by": "fictional-reviewer",
        "reason": "mark ready anyway",
    }
    result = FilingReadyGate().evaluate(payload)
    assert result["filing_ready"] is False
    assert result["mandatory_checks"]["legal_claims_supported"] is False
    assert "claim_not_supported:fictional-partial" in result["blockers"]


@pytest.mark.parametrize("status,supported", [("partially_supported", True), ("supported", False)])
def test_gate_rejects_partial_or_contradictory_fact_support(status, supported):
    payload = _complete_payload()
    payload["facts_mapped_to_evidence"] = True
    payload["fact_to_evidence_map"][0].update(support_status=status, supported=supported)
    result = FilingReadyGate().evaluate(payload)
    assert result["filing_ready"] is False
    assert result["mandatory_checks"]["facts_mapped_to_evidence"] is False


@pytest.mark.parametrize("invalid", ["bad", {"claims": "bad"}, {"claims": ["bad"]}])
def test_malformed_claim_report_fails_closed_without_exception(invalid):
    payload = _complete_payload()
    payload["legal_claims_supported"] = True
    payload["claim_support_report"] = invalid
    result = FilingReadyGate().evaluate(payload)
    assert result["filing_ready"] is False
    assert "claim_support_report_invalid" in result["blockers"]


def test_gate_keeps_fully_supported_positive_control():
    assert FilingReadyGate().evaluate(_complete_payload())["filing_ready"] is True


def test_desktop_api_preserves_partial_status_and_filing_blocker(tmp_path, monkeypatch):
    from maine_family_law_llm.api import app

    root = _authority_root(tmp_path)
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(root))
    claim = "Parental rights and responsibilities are decided according to the best interest of the child and require a purple certificate."
    with TestClient(app) as client:
        response = client.post(
            "/api/authority/verify-answer",
            json={
                "text": "19-A M.R.S. § 1653. " + claim,
                "source_ids": ["statute-19a-1653"],
                "claims": [{"claim": claim, "source_ids": ["statute-19a-1653"]}],
                "auto_extract_claims": False,
            },
        )
        preview = client.get("/api/authority/sources/statute-19a-1653")
    assert response.status_code == 200
    body = response.json()
    assert body["review_required"] is True
    assert body["verification_report"]["claims"][0]["status"] == "partially_supported"
    assert body["verification_report"]["claims"][0]["supported"] is False
    assert "claim_partially_supported" in body["verification_report"]["blockers"]
    assert body["filing_gate"]["filing_ready"] is False
    card = body["verification_report"]["claims"][0]["source_cards"][0]
    assert card["source_id"] == "statute-19a-1653"
    assert preview.status_code == 200
    assert "best interest of the child" in str(preview.json())


def test_release_metrics_count_partial_support_as_blocked_not_passed():
    from legal.evals.claim_support_metrics import BLOCKING_CLAIM_STATUSES, _status_matches

    assert "partially_supported" in BLOCKING_CLAIM_STATUSES
    assert _status_matches("blocked", "partially_supported")
    assert not _status_matches("supported", "partially_supported")
