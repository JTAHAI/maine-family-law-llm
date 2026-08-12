from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.documents.workspace import create_document, propose_revision, commit_revision
from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from legal.forms import MaineFindingsFormsError, MaineFindingsFormsStore
from maine_family_law_llm import api as api_module


def _forms() -> list[dict]:
    return [
        {
            "source_id": "form-fm-001",
            "form_id": "FM-001",
            "title": "FM-001 Complaint for Divorce with Children",
            "citation": "FM-001",
            "source_class": "court_form",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
            "version_date": "07/2026",
            "text": "Docket Number: Plaintiff: Defendant: Child name: Address: Signature: Date:",
            "issue_labels": ["divorce", "parental_rights_responsibilities"],
        },
        {
            "source_id": "form-fm-999",
            "form_id": "FM-999",
            "title": "FM-999 Old form",
            "citation": "FM-999",
            "source_class": "court_form",
            "authority_status": "verified_official_maine",
            "freshness_status": "stale",
            "version_date": "01/2020",
            "text": "Plaintiff: Defendant: Signature:",
        },
    ]


def _records() -> list[dict]:
    return [
        {
            "evidence_id": "record-school",
            "source_locator": r"C:\matter\school-report.pdf",
            "source_hash": "a" * 64,
            "page_number": 2,
            "text": "The child is nine years old and has attended the same school for three years. The school reports stable attendance.",
        },
        {
            "evidence_id": "record-safety",
            "source_locator": "/private/safety-note.pdf",
            "source_hash": "b" * 64,
            "page_number": 4,
            "text": "The report describes a safety risk and recommends supervised contact pending review.",
        },
    ]


def test_findings_engine_builds_factor_matrix_with_exact_record_spans():
    text = "Findings of fact. The child is nine years old. School continuity supports stability."
    report = Rule52BestInterestFindingsEngine().review_order(text, posture="final_order", evidence_records=_records()).to_dict()
    age = next(row for row in report["factor_matrix"] if row["factor_id"] == "child_age")
    school = next(row for row in report["factor_matrix"] if row["factor_id"] == "school_community")
    assert age["status"] == "addressed"
    assert age["draft_spans"][0]["start_offset"] >= 0
    assert age["supporting_record_spans"][0]["safe_locator"] == "school-report.pdf"
    assert school["record_support_status"] == "candidate_spans_found"
    assert report["review_required"] is True


def test_findings_engine_blocks_missing_factors_restrictions_and_delegation():
    text = "Final order on parental rights. Supervised contact shall occur as determined by the therapist. The PFA order is adopted."
    report = Rule52BestInterestFindingsEngine().review_order(text, posture="final_order").to_dict()
    assert "rule52:findings_of_fact_section_missing" in report["blockers"]
    assert "contact_restriction_without_supported_findings" in report["blockers"]
    assert "third_party_parenting_decision_delegation" in report["blockers"]
    assert "pfa_family_overlap_independent_analysis_missing" in report["blockers"]
    assert any(item.startswith("best_interest_factor_missing:") for item in report["blockers"])


def test_review_build_is_revision_bound_immutable_and_reusable(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(
        case,
        title="Proposed parental rights order",
        content="Findings of fact. The child is nine years old. School continuity supports stability. FM-001.",
        document_type="draft",
    )
    store = MaineFindingsFormsStore(case)
    result = store.build_review(
        doc["document_id"],
        authority_forms=_forms(),
        selected_form_ids=["FM-001"],
        posture="final_order",
        evidence_records=_records(),
        approved=True,
    )
    assert result.build_id
    assert result.packet["revision_id"] == doc["current_revision_id"]
    assert result.packet["form_plan"]["selected_form_ids"] == ["FM-001"]
    assert store.verify(result.build_id)["valid"] is True
    reused = store.build_review(
        doc["document_id"],
        authority_forms=_forms(),
        selected_form_ids=["FM-001"],
        posture="final_order",
        evidence_records=_records(),
        approved=True,
    )
    assert reused.build_id == result.build_id
    assert reused.reused_existing_build is True
    assert reused.packet["packet_sha256"] == result.packet["packet_sha256"]


def test_unknown_or_stale_form_remains_blocked(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Motion", content="Motion text.", document_type="motion")
    store = MaineFindingsFormsStore(case)
    none = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=[], posture="post_judgment", approved=True)
    assert "required_form_selection_not_confirmed" in none.blockers
    stale = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=["FM-999"], posture="post_judgment", approved=True)
    assert "form_not_verified_current:FM-999" in stale.blockers


def test_form_completion_requires_fields_detects_cross_form_conflict_and_never_claims_filing_ready(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Complaint", content="Complaint for divorce with children. FM-001.", document_type="court_form_notes")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=["FM-001"], posture="initial_complaint", approved=True)
    completed = store.complete_forms(
        review.build_id,
        form_values={"FM-001": {"plaintiff_name": "Alex Example", "defendant_name": "Jordan Example", "signature": "Alex Example"}},
        confirmed=True,
    )
    assert completed["filing_ready"] is False
    assert completed["review_required"] is True
    assert any(item.startswith("required_form_field_missing:FM-001:") for item in completed["completion"]["blockers"])
    names = {row["name"] for row in completed["artifacts"]}
    assert {"form-working-copy.json", "form-working-copy.txt", "form-completion-receipt.json"} <= names


def test_completion_refuses_stale_document_revision(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Complaint", content="FM-001.", document_type="court_form_notes")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=["FM-001"], posture="initial_complaint", approved=True)
    proposal = propose_revision(case, doc["document_id"], content="Changed FM-001.", base_revision_id=doc["current_revision_id"])
    commit_revision(case, doc["document_id"], revision_id=proposal["revision_id"], confirmation_token=proposal["confirmation_token"], confirmed=True)
    with pytest.raises(MaineFindingsFormsError, match="changed"):
        store.complete_forms(review.build_id, form_values={"FM-001": {}}, confirmed=True)


def test_tampered_review_artifact_fails_verification(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Order", content="Findings of fact.", document_type="draft")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=["FM-001"], approved=True)
    path = store.builds / review.build_id / "maine-findings-forms-review.json"
    payload = json.loads(path.read_text())
    payload["document_title"] = "Tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    verification = store.verify(review.build_id)
    assert verification["status"] == "fail"
    assert any(item.startswith("artifact_hash_mismatch") for item in verification["blockers"])


def test_api_routes_and_artifact_capabilities(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Proposed order", content="Findings of fact. Child age and school stability. FM-001.", document_type="draft")
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda root: _records())
    monkeypatch.setattr(api_module.AuthorityProductService, "list_forms", lambda self, **kwargs: {"status": "pass", "build_id": "a" * 24, "forms": _forms(), "count": 2})
    client = TestClient(api_module.app)

    status = client.get(f"/api/findings-forms/status?document_id={doc['document_id']}")
    assert status.status_code == 200
    assert status.json()["catalog"]["form_count"] == 2

    review = client.post(
        f"/api/findings-forms/documents/{doc['document_id']}/review",
        json={"selected_form_ids": ["FM-001"], "posture": "final_order", "approved": True},
    )
    assert review.status_code == 200
    review_payload = review.json()
    assert review_payload["build_id"]
    assert all("relative_path" not in row for row in review_payload["artifacts"])
    artifact = client.get(review_payload["artifacts"][0]["download_url"])
    assert artifact.status_code == 200

    completion = client.post(
        "/api/findings-forms/complete",
        json={"build_id": review_payload["build_id"], "form_values": {"FM-001": {"plaintiff_name": "A"}}, "confirmed": True},
    )
    assert completion.status_code == 200
    assert completion.json()["filing_ready"] is False


def test_v5110_exact_findings_and_forms_alias_routes(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Proposed order", content="Findings of fact. School continuity supports stability. FM-001.", document_type="draft")
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda root: _records())
    monkeypatch.setattr(api_module.AuthorityProductService, "list_forms", lambda self, **kwargs: {"status": "pass", "build_id": "a" * 24, "forms": _forms(), "count": 2})
    client = TestClient(api_module.app)

    matrix = client.post(
        "/api/findings/matrix/build",
        json={"document_id": doc["document_id"], "selected_form_ids": ["FM-001"], "posture": "final_order", "approved": True},
    )
    assert matrix.status_code == 200
    matrix_payload = matrix.json()
    assert matrix_payload["matrix"]
    element_id = matrix_payload["matrix"][0]["factor_id"]

    list_matrix = client.get("/api/findings/matrix")
    assert list_matrix.status_code == 200
    assert list_matrix.json()["matrix"]

    patched = client.patch(
        f"/api/findings/matrix/{element_id}",
        json={
            "build_id": matrix_payload["build_id"],
            "reviewer_status": "needs_review",
            "reviewer_notes": "Check the school record span.",
            "proposed_finding": "School continuity is a contested factor.",
            "supporting_record_ids": ["record-school"],
            "contrary_record_ids": ["record-safety"],
            "approved": True,
        },
    )
    assert patched.status_code == 200
    history = client.get(f"/api/findings/matrix/{element_id}/history", params={"build_id": matrix_payload["build_id"]})
    assert history.status_code == 200
    assert history.json()["history"]

    restriction = client.post(
        "/api/findings/restrictions/review",
        json={
            "proposed_restriction_language": "Supervised contact shall occur as determined by the therapist.",
            "document_id": doc["document_id"],
            "selected_record_ids": ["record-safety"],
            "posture": "final_order",
            "approved": True,
        },
    )
    assert restriction.status_code == 200
    assert restriction.json()["review_required"] is True

    forms = client.get("/api/forms", params={"proceeding_type": "family_matter"})
    assert forms.status_code == 200
    assert forms.json()["forms"]
    entry = client.get("/api/forms/FM-001")
    assert entry.status_code == 200
    assert entry.json()["form"]["form_id"] == "FM-001"

    session = client.post(
        "/api/forms/session",
        json={"document_id": doc["document_id"], "proceeding_type": "family_matter", "selected_form_ids": ["FM-001"], "approved": True},
    )
    assert session.status_code == 200
    session_id = session.json()["session_id"]
    patched_session = client.patch(
        f"/api/forms/session/{session_id}",
        json={"form_values": {"FM-001": {"plaintiff_name": "Alex Example"}}, "reviewer_notes": "Preview the insertion.", "approved": True},
    )
    assert patched_session.status_code == 200
    validated = client.post(
        f"/api/forms/session/{session_id}/validate",
        json={"form_values": {"FM-001": {"plaintiff_name": "Alex Example"}}, "confirmed": True},
    )
    assert validated.status_code == 200
    generated = client.post(
        f"/api/forms/session/{session_id}/generate",
        json={"form_values": {"FM-001": {"plaintiff_name": "Alex Example"}}, "confirmed": True},
    )
    assert generated.status_code == 200
    receipt = client.get(f"/api/forms/session/{session_id}/receipt")
    assert receipt.status_code == 200
    assert receipt.json()["receipt"]["schema_version"] == "maine_form_completion_receipt_v1"


def test_review_ledger_includes_findings_report(monkeypatch, tmp_path: Path):
    from legal.review import prepare_review_request

    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Proposed order", content="Final order on parental rights. Supervised contact.", document_type="draft")
    authority = {
        "status": "blocked",
        "filing_gate": {"mandatory_checks": {}},
        "verification_report": {"claims": [], "citations": [], "quotes": []},
        "sources": [],
    }
    packet = prepare_review_request(case, doc["document_id"], authority_result=authority, records=_records())["packet"]
    assert "findings_review" in packet
    assert packet["findings_review"]["review_required"] is True
    assert any(item.startswith("best_interest_factor_missing:") for item in packet["filing_gate_preflight"]["blockers"])

def test_v5110_main_workbench_exposes_findings_forms_controls_and_routes():
    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    for marker in (
        'id="findings-forms-status-badge"',
        'id="findings-forms-catalog"',
        'id="findings-forms-approved"',
        'id="findings-forms-build"',
        'id="findings-forms-results"',
        'id="findings-forms-fields"',
        'id="findings-forms-complete"',
    ):
        assert marker in html
    for route in (
        "/api/findings-forms/status",
        "/api/findings-forms/documents/",
        "/api/findings-forms/complete",
    ):
        assert route in js
    assert "renderFindingsFormsReview" in js
    assert "collectFindingsFormsValues" in js
    assert ".findings-factor-matrix" in css
    assert ".findings-form-choice" in css


def test_tampered_completion_fails_independent_verification(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Complaint", content="FM-001.", document_type="court_form_notes")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(doc["document_id"], authority_forms=_forms(), selected_form_ids=["FM-001"], posture="initial_complaint", approved=True)
    completed = store.complete_forms(review.build_id, form_values={"FM-001": {"plaintiff_name": "A"}}, confirmed=True)
    path = store.builds / review.build_id / "completions" / completed["completion_id"] / "form-working-copy.txt"
    path.write_text("tampered", encoding="utf-8")
    verification = store.verify_completion(review.build_id, completed["completion_id"])
    assert verification["status"] == "fail"
    assert any(item.startswith("completion_artifact_") for item in verification["blockers"])


def test_existing_tampered_completion_is_not_reused(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Complaint", content="FM-001.", document_type="court_form_notes")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(
        doc["document_id"],
        authority_forms=_forms(),
        selected_form_ids=["FM-001"],
        posture="initial_complaint",
        approved=True,
    )
    values = {"FM-001": {"plaintiff_name": "A"}}
    completed = store.complete_forms(review.build_id, form_values=values, confirmed=True)
    path = store.builds / review.build_id / "completions" / completed["completion_id"] / "form-working-copy.txt"
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(MaineFindingsFormsError, match="failed verification"):
        store.complete_forms(review.build_id, form_values=values, confirmed=True)


def test_completion_verification_propagates_parent_review_tamper(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    doc = create_document(case, title="Complaint", content="FM-001.", document_type="court_form_notes")
    store = MaineFindingsFormsStore(case)
    review = store.build_review(
        doc["document_id"],
        authority_forms=_forms(),
        selected_form_ids=["FM-001"],
        posture="initial_complaint",
        approved=True,
    )
    completed = store.complete_forms(review.build_id, form_values={"FM-001": {"plaintiff_name": "A"}}, confirmed=True)
    review_path = store.builds / review.build_id / "maine-findings-forms-review.html"
    review_path.write_text("tampered", encoding="utf-8")
    verification = store.verify_completion(review.build_id, completed["completion_id"])
    assert verification["status"] == "fail"
    assert any(item.startswith("parent_review:") for item in verification["blockers"])
