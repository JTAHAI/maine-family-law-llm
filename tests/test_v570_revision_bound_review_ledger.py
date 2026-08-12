from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.documents.workspace import commit_revision, create_document, propose_revision
from legal.review import (
    ReviewLedgerError,
    commit_review_decision,
    list_review_history,
    prepare_review_request,
    verify_review_ledger,
)


def _authority_result() -> dict:
    return {
        "status": "verified_pending_human_review",
        "authority_build_id": "a" * 24,
        "verification_report": {
            "citations": [{"citation": "19-A M.R.S. § 1653", "status": "found"}],
            "quotes": [{"source_id": "statute-1653", "status": "exact_match", "start_offset": 4, "end_offset": 22}],
            "claims": [{"claim": "The court considers best-interest factors.", "status": "supported"}],
            "blockers": [],
        },
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": True,
                "citations_resolved": True,
                "quotes_found": True,
                "legal_claims_supported": True,
                "facts_mapped_to_evidence": False,
                "procedure_posture_checked": False,
                "forms_current": False,
                "human_review_complete": False,
            },
            "blockers": ["facts_mapped_to_evidence", "procedure_posture_checked", "forms_current", "human_review_complete"],
        },
        "verification_receipt": {"receipt_sha256": "b" * 64},
        "review_required": True,
    }


def _record() -> dict:
    text = "On 01/03/2026 the child moved to a new school after the winter break."
    return {
        "evidence_id": "record-1",
        "title": "School notice",
        "source_locator": r"C:\private\matter\school-notice.txt",
        "source_hash": "c" * 64,
        "page_number": 1,
        "text_excerpt": text,
    }


def _case(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    root.mkdir()
    return root


def test_review_packet_binds_revision_authority_fact_spans_and_one_use_token(tmp_path: Path):
    case = _case(tmp_path)
    document = create_document(
        case,
        title="Motion review",
        content="The court considers best-interest factors. 19-A M.R.S. § 1653",
        document_type="motion",
    )
    prepared = prepare_review_request(
        case,
        document["document_id"],
        authority_result=_authority_result(),
        facts=["On 01/03/2026 the child moved to a new school"],
        records=[_record()],
    )

    packet = prepared["packet"]
    assert packet["revision_id"] == document["current_revision_id"]
    assert packet["document_content_sha256"] == document["content_sha256"]
    assert packet["fact_evidence_report"]["supported_count"] == 1
    support = packet["fact_evidence_report"]["facts"][0]["supporting_records"][0]
    assert support["evidence_id"] == "record-1"
    assert support["source_locator"] == "school-notice.txt"
    assert support["span_start"] >= 0
    assert len(packet["packet_sha256"]) == 64

    decision = commit_review_decision(
        case,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="approve_review",
        reviewer_name="Local reviewer",
        reviewer_role="attorney",
        attested=True,
        notes="Reviewed the exact revision and reports.",
    )
    assert decision["packet_sha256"] == packet["packet_sha256"]
    assert decision["status"] == "review_complete_blocked"
    assert "procedure_posture_checked" in decision["filing_gate"]["blockers"]
    assert decision["filing_gate"]["filing_ready"] is False
    assert verify_review_ledger(case, document["document_id"])["valid"] is True

    with pytest.raises(ReviewLedgerError, match="already been used"):
        commit_review_decision(
            case,
            document["document_id"],
            request_id=prepared["request_id"],
            confirmation_token=prepared["confirmation_token"],
            confirmed=True,
            decision="approve_review",
            reviewer_name="Local reviewer",
            reviewer_role="attorney",
            attested=True,
        )


def test_review_request_fails_closed_if_document_revision_changes(tmp_path: Path):
    case = _case(tmp_path)
    document = create_document(case, title="Draft", content="Original", document_type="draft")
    prepared = prepare_review_request(case, document["document_id"], authority_result=_authority_result())
    proposal = propose_revision(
        case,
        document["document_id"],
        content="Changed",
        base_revision_id=document["current_revision_id"],
    )
    commit_revision(
        case,
        document["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )

    with pytest.raises(ReviewLedgerError, match="changed after"):
        commit_review_decision(
            case,
            document["document_id"],
            request_id=prepared["request_id"],
            confirmation_token=prepared["confirmation_token"],
            confirmed=True,
            decision="request_changes",
            reviewer_name="Reviewer",
            reviewer_role="other_reviewer",
            attested=False,
        )


def test_review_ledger_detects_tampering(tmp_path: Path):
    case = _case(tmp_path)
    document = create_document(case, title="Draft", content="Text", document_type="draft")
    prepared = prepare_review_request(case, document["document_id"], authority_result=_authority_result())
    decision = commit_review_decision(
        case,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="request_changes",
        reviewer_name="Reviewer",
        reviewer_role="paralegal",
        attested=False,
        notes="Add the missing form review.",
    )
    history = list_review_history(case, document["document_id"])
    assert history["decision_count"] == 1
    decision_path = case / "19_DOCUMENT_WORKSPACE" / "reviews" / document["document_id"] / "decisions" / f"{decision['decision_id']}.json"
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    payload["notes"] = "tampered"
    decision_path.write_text(json.dumps(payload), encoding="utf-8")
    report = verify_review_ledger(case, document["document_id"])
    assert report["valid"] is False
    assert any(item.startswith("decision_hash_mismatch:") for item in report["blockers"])


def test_review_request_hash_tampering_fails_closed(tmp_path: Path):
    case = _case(tmp_path)
    document = create_document(case, title="Draft", content="Text", document_type="draft")
    prepared = prepare_review_request(case, document["document_id"], authority_result=_authority_result())
    request_path = case / "19_DOCUMENT_WORKSPACE" / "reviews" / document["document_id"] / "requests" / f"{prepared['request_id']}.json"
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    payload["packet"]["document_title"] = "tampered"
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReviewLedgerError, match="integrity check"):
        commit_review_decision(
            case,
            document["document_id"],
            request_id=prepared["request_id"],
            confirmation_token=prepared["confirmation_token"],
            confirmed=True,
            decision="request_changes",
            reviewer_name="Reviewer",
            reviewer_role="paralegal",
            attested=False,
        )
