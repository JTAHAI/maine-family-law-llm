"""API integration tests for guarded local document handling."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    return TestClient(api.app)


def test_document_api_create_propose_commit_and_export(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    created_response = client.post(
        "/api/document-workspace/documents",
        json={"title": "Parenting plan working draft", "content": "First line\nSecond line", "document_type": "parenting_plan"},
    )
    assert created_response.status_code == 200
    created = created_response.json()["document"]
    document_id = created["document_id"]
    original_revision = created["current_revision_id"]

    proposal_response = client.post(
        f"/api/document-workspace/documents/{document_id}/proposals",
        json={"content": "First line\nRevised line", "base_revision_id": original_revision, "note": "User-reviewed update"},
    )
    assert proposal_response.status_code == 200
    proposal = proposal_response.json()["proposal"]
    assert proposal["diff"]["changes_count"] == 2

    refused = client.post(
        f"/api/document-workspace/documents/{document_id}/commit",
        json={"revision_id": proposal["revision_id"], "confirmation_token": proposal["confirmation_token"], "confirmed": False},
    )
    assert refused.status_code == 409

    committed = client.post(
        f"/api/document-workspace/documents/{document_id}/commit",
        json={"revision_id": proposal["revision_id"], "confirmation_token": proposal["confirmation_token"], "confirmed": True},
    )
    assert committed.status_code == 200
    row = committed.json()["document"]
    assert row["content"].endswith("Revised line")
    assert row["original_revision_id"] == original_revision
    assert row["original_preserved"] is True

    txt_session = client.post(f"/api/document-workspace/documents/{document_id}/export-sessions?format=txt")
    assert txt_session.status_code == 200
    txt = client.get(txt_session.json()["download_url"])
    assert txt.status_code == 200
    assert b"Revised line" in txt.content
    assert txt.headers["x-mfll-filing-gate-status"] == "review_required"
    assert txt.headers["x-mfll-filing-gate-blockers"] == "review_packet_missing"
    word_session = client.post(f"/api/document-workspace/documents/{document_id}/export-sessions?format=docx")
    assert word_session.status_code == 200
    word = client.get(word_session.json()["download_url"])
    assert word.status_code == 200
    assert word.content.startswith(b"PK")
    assert word.headers["x-content-type-options"] == "nosniff"
    assert word.headers["x-mfll-filing-gate-status"] == "review_required"


def test_document_api_soft_delete_is_two_phase_and_restoreable(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)
    document = client.post("/api/document-workspace/documents", json={"title": "Memo", "content": "Text"}).json()["document"]
    document_id = document["document_id"]

    request = client.post(f"/api/document-workspace/documents/{document_id}/delete-request")
    assert request.status_code == 200
    token = request.json()["confirmation_token"]
    refused = client.post(f"/api/document-workspace/documents/{document_id}/delete", json={"confirmation_token": token, "confirmed": False})
    assert refused.status_code == 409

    deleted = client.post(f"/api/document-workspace/documents/{document_id}/delete", json={"confirmation_token": token, "confirmed": True})
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    restored = client.post(f"/api/document-workspace/documents/{document_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["document"]["status"] == "review_required"


def test_document_api_status_exposes_local_security_contract(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)
    response = client.get("/api/document-workspace/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["local_only"] is True
    assert payload["originals_immutable"] is True
    assert payload["explicit_confirmation_required"] is True
    assert payload["audit_chain"]["valid"] is True
    assert payload["docx"]["license"] == "MIT"
