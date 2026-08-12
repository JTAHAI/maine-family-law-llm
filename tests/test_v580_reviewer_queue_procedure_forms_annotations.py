from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.documents.workspace import commit_revision, create_document, propose_revision
from legal.review import (
    ReviewLedgerError,
    build_form_freshness_report,
    build_procedure_posture_report,
    build_reviewer_queue,
    commit_review_decision,
    prepare_review_request,
)
from maine_family_law_llm import api as api_module


def _authority_result(*, with_claim: bool = True, form_status: str = "current") -> dict:
    claims = []
    if with_claim:
        claims = [{
            "claim_id": "claim-001",
            "statement": "The draft requests enforcement of the current order.",
            "support_status": "supported",
            "claim_type": "legal",
            "source_ids": ["authority-order-enforcement"],
        }]
    return {
        "status": "review_required",
        "sources": [{
            "source_id": "form-fm-001",
            "title": "Maine court form FM-001",
            "source_class": "court_form",
            "freshness_status": form_status,
            "version_date": "07/2026",
        }],
        "verification_report": {"citations": [], "quotes": [], "claims": claims, "blockers": []},
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": True,
                "citations_resolved": True,
                "quotes_found": True,
                "legal_claims_supported": True,
            },
            "blockers": [],
        },
        "review_required": True,
    }


def test_procedure_report_detects_contempt_and_form_review_requirement():
    report = build_procedure_posture_report(
        title="Motion for Contempt",
        content="This motion for contempt concerns an existing final order.",
        document_type="motion",
    )
    assert report["status"] == "checked"
    assert report["procedural_posture"] == "motion_for_contempt"
    assert report["form_review_required"] is True
    assert any("exact current order" in item for item in report["review_items"])


def test_ambiguous_or_unknown_procedure_fails_closed():
    report = build_procedure_posture_report(title="Working draft", content="General notes only.", document_type="draft")
    assert report["status"] == "review_required"
    assert "procedure_posture_not_identified" in report["blockers"]


def test_form_report_requires_admitted_current_source_and_blocks_missing_selection():
    procedure = build_procedure_posture_report(
        title="Motion for Contempt", content="Motion for contempt", document_type="motion"
    )
    current = build_form_freshness_report(
        content="Use FM-001 for this filing.", authority_result=_authority_result(), procedure_report=procedure
    )
    assert current["status"] == "checked"
    assert current["current_forms"] == ["FM-001"]

    missing = build_form_freshness_report(content="No form selected.", authority_result={}, procedure_report=procedure)
    assert missing["status"] == "review_required"
    assert "required_form_selection_not_confirmed" in missing["unknown_forms"]


def test_review_packet_contains_claims_procedure_forms_and_requires_claim_annotations(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(
        case,
        title="Motion for Contempt",
        content="Motion for contempt. The draft requests enforcement of the current order. Use FM-001.",
        document_type="motion",
    )
    prepared = prepare_review_request(case, document["document_id"], authority_result=_authority_result())
    packet = prepared["packet"]
    assert packet["procedure_posture_report"]["procedural_posture"] == "motion_for_contempt"
    assert packet["forms_report"]["current_forms"] == ["FM-001"]
    assert packet["claims_for_review"][0]["claim_id"] == "claim-001"

    decision = commit_review_decision(
        case,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="approve_review",
        reviewer_name="Reviewer",
        reviewer_role="attorney",
        attested=True,
        claim_annotations=[],
    )
    assert decision["status"] == "review_complete_blocked"
    assert "review_annotation_missing:claim-001" in decision["filing_gate"]["blockers"]


def test_blocking_claim_annotation_is_immutable_gate_blocker(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(
        case,
        title="Motion for Contempt",
        content="Motion for contempt. The draft requests enforcement of the current order. Use FM-001.",
        document_type="motion",
    )
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
        claim_annotations=[{"claim_id": "claim-001", "status": "needs_authority", "note": "Add controlling authority."}],
    )
    assert decision["claim_annotations"][0]["status"] == "needs_authority"
    assert "review_annotation:claim-001:needs_authority" in decision["filing_gate"]["blockers"]


def test_unknown_or_duplicate_claim_annotations_are_refused(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(case, title="Motion for Contempt", content="Motion for contempt. FM-001", document_type="motion")
    prepared = prepare_review_request(case, document["document_id"], authority_result=_authority_result())
    with pytest.raises(ReviewLedgerError, match="unknown claim"):
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
            claim_annotations=[{"claim_id": "claim-does-not-exist", "status": "unsupported"}],
        )


def test_reviewer_queue_surfaces_pending_and_stale_reviews(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    pending_doc = create_document(case, title="Pending motion", content="Motion for contempt. FM-001", document_type="motion")
    prepare_review_request(case, pending_doc["document_id"], authority_result=_authority_result(with_claim=False))

    stale_doc = create_document(case, title="Changed motion", content="Motion to modify. FM-001", document_type="motion")
    prepared = prepare_review_request(case, stale_doc["document_id"], authority_result=_authority_result(with_claim=False))
    commit_review_decision(
        case,
        stale_doc["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="request_changes",
        reviewer_name="Reviewer",
        reviewer_role="paralegal",
        attested=False,
    )
    proposal = propose_revision(case, stale_doc["document_id"], content="Motion to modify changed. FM-001", base_revision_id=stale_doc["current_revision_id"])
    commit_revision(case, stale_doc["document_id"], revision_id=proposal["revision_id"], confirmation_token=proposal["confirmation_token"], confirmed=True)

    queue = build_reviewer_queue(case)
    by_title = {row["title"]: row for row in queue["items"]}
    assert by_title["Pending motion"]["queue_status"] == "awaiting_reviewer"
    assert by_title["Changed motion"]["queue_status"] == "stale_review_after_revision_change"
    assert by_title["Pending motion"]["packet_summary"]["procedural_posture"] == "motion_for_contempt"


def test_v580_api_and_ui_expose_queue_and_claim_annotations(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(case, title="Motion for Contempt", content="Motion for contempt. FM-001", document_type="motion")
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module.AuthorityProductService, "verify_output", lambda self, **kwargs: _authority_result())
    client = TestClient(api_module.app)

    prepared = client.post(f"/api/document-workspace/documents/{document['document_id']}/review/prepare", json={"facts": []})
    assert prepared.status_code == 200
    assert prepared.json()["packet"]["claims_for_review"][0]["claim_id"] == "claim-001"

    queue = client.get("/api/document-workspace/review-queue")
    assert queue.status_code == 200
    assert queue.json()["items"][0]["queue_status"] == "awaiting_reviewer"

    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="document-review-queue"' in html
    assert 'id="document-claim-annotations"' in html
    assert "/api/document-workspace/review-queue" in js
    assert "collectClaimAnnotations" in js
    assert ".document-review-queue-item" in css
