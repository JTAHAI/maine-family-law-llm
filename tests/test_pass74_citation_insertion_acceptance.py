from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.citation_insertion import CitationInsertionStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module


def _authority(*, freshness: str = "fresh") -> dict[str, str]:
    return {
        "source_id": "fictional-official-source",
        "source_hash": "b" * 64,
        "citation": "Fictional Maine Rule",
        "pinpoint": "§ 4",
        "exact_span": "Fictional Maine Rule § 4 requires reviewer confirmation.",
        "freshness_status": freshness,
    }


def _document() -> dict[str, str]:
    return {"document_id": "f" * 32, "current_revision_id": "e" * 32, "content": "Fictional Rule requires reviewer confirmation."}


def _resolved_source() -> dict[str, object]:
    """A fictional local resolver result; never a client-provided authority card."""
    authority = _authority()
    return {
        "source_card": {
            "source_hash": authority["source_hash"],
            "citation": authority["citation"],
            "title": "Fictional official source",
            "source_span_preview": authority["exact_span"],
            "source_span": {"pinpoint": authority["pinpoint"]},
            "freshness_status": authority["freshness_status"],
        }
    }


def test_pass74_creates_encrypted_hash_bound_proposal_without_mutating_draft(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = CitationInsertionStore(root, encryption_key="fictional-test-key")
    receipt = store.create({"reviewer_safe_id": "reviewer_001", "selected_text": "Fictional Rule requires reviewer confirmation.", "authority": _authority(), "user_confirmed": True}, document=_document())
    assert receipt["review_required"] is True and receipt["filing_ready"] is False
    assert receipt["proposed_content"] == "Fictional Rule requires reviewer confirmation. (Fictional Maine Rule, § 4)"
    assert receipt["authority"]["source_hash"] == "b" * 64
    assert "Fictional Rule requires" not in store.path.read_text(encoding="utf-8")


def test_pass74_refuses_unconfirmed_stale_and_unverified_pinpoints(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); store = CitationInsertionStore(root, encryption_key="fictional-test-key")
    cases = [
        ({"reviewer_safe_id": "reviewer_001", "selected_text": "Fictional Rule requires reviewer confirmation.", "authority": _authority(), "user_confirmed": False}, "citation_insertion_confirmation_required"),
        ({"reviewer_safe_id": "reviewer_001", "selected_text": "Fictional Rule requires reviewer confirmation.", "authority": _authority(freshness="stale"), "user_confirmed": True}, "citation_authority_stale"),
        ({"reviewer_safe_id": "reviewer_001", "selected_text": "Fictional Rule requires reviewer confirmation.", "authority": _authority() | {"pinpoint": ""}, "user_confirmed": True}, "verified_pinpoint_required"),
    ]
    for payload, code in cases:
        try:
            store.create(payload, document=_document())
        except Exception as exc:
            assert str(exc) == code
        else:
            raise AssertionError(code)


def test_pass74_does_not_duplicate_a_full_citation_used_as_the_source_locator(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir()
    receipt = CitationInsertionStore(root, encryption_key="fictional-test-key").create(
        {
            "reviewer_safe_id": "reviewer_001",
            "selected_text": _document()["content"],
            "authority": _authority() | {"pinpoint": "Fictional Maine Rule"},
            "user_confirmed": True,
        },
        document=_document(),
    )
    assert receipt["proposed_content"].endswith(" (Fictional Maine Rule)")


def test_pass74_canonical_api_creates_only_reviewable_revision_proposal(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "inspect_source", lambda source_id: _resolved_source())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(root, title="Fictional citation draft", content=_document()["content"], document_type="draft")
    client = TestClient(api_module.app)
    created = client.post(f"/api/drafting/documents/{document['document_id']}/citation-insertions", json={"reviewer_safe_id": "reviewer_001", "selected_text": "Fictional Rule requires reviewer confirmation.", "authority": _authority(), "user_confirmed": True})
    assert created.status_code == 200
    receipt = created.json()["receipt"]
    proposed = client.post(f"/api/drafting/documents/{document['document_id']}/citation-insertions/{receipt['receipt_id']}/propose")
    assert proposed.status_code == 200
    assert proposed.json()["original_preserved"] is True and proposed.json()["proposal"]["review_required"] is True
    current = client.get(f"/api/document-workspace/documents/{document['document_id']}").json()["document"]
    assert current["content"] == _document()["content"]


def test_pass74_canonical_api_rejects_client_authority_tampering(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "inspect_source", lambda source_id: _resolved_source())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(root, title="Fictional citation draft", content=_document()["content"], document_type="draft")
    result = TestClient(api_module.app).post(
        f"/api/drafting/documents/{document['document_id']}/citation-insertions",
        json={
            "reviewer_safe_id": "reviewer_001",
            "selected_text": _document()["content"],
            "authority": _authority() | {"source_hash": "c" * 64, "pinpoint": "invented"},
            "user_confirmed": True,
        },
    )
    assert result.status_code == 409
    assert result.json()["detail"] == "citation_insertion_authority_hash_mismatch"


def test_pass74_ships_mirrored_production_citation_control() -> None:
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Citation insertion assistant" in text and "/citation-insertions" in text
