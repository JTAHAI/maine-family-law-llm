from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module


def _authority_result() -> dict:
    return {
        "status": "review_required",
        "verification_report": {"citations": [], "quotes": [], "claims": [], "blockers": ["citation_not_found"]},
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": False,
                "citations_resolved": False,
                "quotes_found": False,
                "legal_claims_supported": False,
            },
            "blockers": ["authority_verified", "citations_resolved", "quotes_found", "legal_claims_supported"],
        },
        "review_required": True,
    }


def test_v570_workbench_exposes_revision_bound_review_controls_and_endpoints():
    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")

    assert 'id="document-review-prepare"' in html
    assert 'id="document-review-commit"' in html
    assert 'id="document-review-facts"' in html
    assert "review/prepare" in js
    assert "review/commit" in js
    assert "A review decision cannot override unresolved filing blockers" in js
    assert ".document-review-packet" in css


def test_v570_local_api_prepares_and_commits_bound_review(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    document = create_document(case, title="Review me", content="Draft text", document_type="motion")
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module.AuthorityProductService, "verify_output", lambda self, **kwargs: _authority_result())
    client = TestClient(api_module.app)

    prepared = client.post(
        f"/api/document-workspace/documents/{document['document_id']}/review/prepare",
        json={"facts": ["A material fact"]},
    )
    assert prepared.status_code == 200
    payload = prepared.json()
    assert payload["status"] == "review_prepared"
    assert payload["packet"]["revision_id"] == document["current_revision_id"]

    committed = client.post(
        f"/api/document-workspace/documents/{document['document_id']}/review/commit",
        json={
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
            "confirmed": True,
            "decision": "request_changes",
            "reviewer_name": "Reviewer",
            "reviewer_role": "paralegal",
            "attested": False,
            "notes": "Resolve the authority blockers.",
        },
    )
    assert committed.status_code == 200
    assert committed.json()["status"] == "changes_requested"

    history = client.get(f"/api/document-workspace/documents/{document['document_id']}/reviews")
    assert history.status_code == 200
    assert history.json()["decision_count"] == 1

    verified = client.get(f"/api/document-workspace/documents/{document['document_id']}/reviews/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
