from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.quote_safe_drafting import QuoteSafeDraftStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module


def _authority() -> dict[str, str]:
    return {"source_id": "fictional-official-source", "source_hash": "b" * 64, "citation": "Fictional Maine Rule", "exact_span": "The fictional court must review the record before action.", "freshness_status": "fresh"}


def _document() -> dict[str, str]:
    return {"document_id": "f" * 32, "current_revision_id": "e" * 32, "content": "The fictional court reviews the record."}


def _resolved_source() -> dict[str, object]:
    authority = _authority()
    return {
        "source_card": {
            "source_hash": authority["source_hash"],
            "citation": authority["citation"],
            "title": "Fictional official source",
            "source_span_preview": authority["exact_span"],
            "source_span": {"pinpoint": "§ 4"},
            "freshness_status": authority["freshness_status"],
        }
    }


def test_pass75_creates_encrypted_exact_quote_proposal(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); store = QuoteSafeDraftStore(root, encryption_key="fictional-test-key")
    receipt = store.create({"reviewer_safe_id": "reviewer_001", "selected_text": "The fictional court reviews the record.", "quote_text": "The fictional court must review the record before action.", "authority": _authority(), "user_confirmed": True}, document=_document())
    assert receipt["quote"]["status"] == "exact" and receipt["review_required"] is True
    assert receipt["proposed_content"] == "“The fictional court must review the record before action.”"
    assert "fictional court" not in store.path.read_text(encoding="utf-8")


def test_pass75_blocks_fuzzy_and_requires_normalized_approval(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); store = QuoteSafeDraftStore(root, encryption_key="fictional-test-key")
    base = {"reviewer_safe_id": "reviewer_001", "selected_text": "The fictional court reviews the record.", "authority": _authority(), "user_confirmed": True}
    for quote, approved, code in [("The fictional court may review something else.", False, "quote_not_found_in_selected_source_span"), ("the fictional court must review the record before action.", False, "normalized_quote_approval_required")]:
        try: store.create(base | {"quote_text": quote, "normalized_quote_approved": approved}, document=_document())
        except Exception as exc: assert str(exc) == code
        else: raise AssertionError(code)


def test_pass75_canonical_api_proposes_without_mutating_original(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); monkeypatch.setattr(api_module, "active_case_root", lambda: root); monkeypatch.setattr(api_module, "inspect_source", lambda source_id: _resolved_source()); monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(root, title="Fictional quote draft", content=_document()["content"], document_type="draft"); client = TestClient(api_module.app)
    created = client.post(f"/api/drafting/documents/{document['document_id']}/quote-receipts", json={"reviewer_safe_id":"reviewer_001", "selected_text":_document()["content"], "quote_text":"The fictional court must review the record before action.", "authority":_authority(), "user_confirmed":True})
    assert created.status_code == 200
    proposed = client.post(f"/api/drafting/documents/{document['document_id']}/quote-receipts/{created.json()['receipt']['receipt_id']}/propose")
    assert proposed.status_code == 200 and proposed.json()["original_preserved"] is True
    assert client.get(f"/api/document-workspace/documents/{document['document_id']}").json()["document"]["content"] == _document()["content"]


def test_pass75_canonical_api_rejects_client_authority_tampering(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); monkeypatch.setattr(api_module, "active_case_root", lambda: root); monkeypatch.setattr(api_module, "inspect_source", lambda source_id: _resolved_source()); monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(root, title="Fictional quote draft", content=_document()["content"], document_type="draft")
    result = TestClient(api_module.app).post(
        f"/api/drafting/documents/{document['document_id']}/quote-receipts",
        json={"reviewer_safe_id":"reviewer_001", "selected_text":_document()["content"], "quote_text":"The fictional court must review the record before action.", "authority":_authority() | {"source_hash": "c" * 64}, "user_confirmed":True},
    )
    assert result.status_code == 409
    assert result.json()["detail"] == "quote_safe_authority_hash_mismatch"


def test_pass75_ships_mirrored_quote_safe_control() -> None:
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Quote-safe drafting" in text and "/quote-receipts" in text
