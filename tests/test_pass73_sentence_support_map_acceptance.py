from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.sentence_support_map import SentenceSupportMapStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [{
        "evidence_id": "RECORD-FICTION-001",
        "title": "Fictional exchange communication",
        "source_locator": "fictional-exchange-message.txt",
        "source_hash": "a" * 64,
        "text": "Fictional parent missed exchange on Tuesday. The fictional parent did not provide notice.",
        "page_number": 1,
    }]


def _authority(*, freshness: str = "fresh") -> list[dict[str, str]]:
    return [{
        "authority_id": "authority_001",
        "source_id": "fictional-official-source",
        "source_hash": "b" * 64,
        "citation": "Fictional Maine Rule fixture",
        "title": "Fictional official authority fixture",
        "exact_span": "Under Maine Rule fixture, fictional review is required unless an exception applies.",
        "freshness_status": freshness,
    }]


def _document() -> dict[str, str]:
    return {
        "document_id": "f" * 32,
        "current_revision_id": "e" * 32,
        "content": "Fictional parent missed exchange on Tuesday. Under Maine Rule fixture, fictional review is required.",
    }


def test_pass73_maps_every_sentence_to_separate_review_signals_in_encrypted_state(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = SentenceSupportMapStore(root, encryption_key="fictional-test-key")
    mapped = store.create_map(
        {"reviewer_safe_id": "reviewer_001", "selected_authority": _authority(), "user_confirmed": True},
        document=_document(), records=_records(),
    )
    assert mapped["review_required"] is True and mapped["filing_ready"] is False
    assert mapped["summary"]["sentence_count"] == 2
    factual, legal = mapped["sentences"]
    assert factual["sentence_kind"] == "factual_or_narrative"
    assert factual["supports"][0]["lane"] == "private_matter_record"
    assert legal["sentence_kind"] == "legal_or_procedural"
    assert any(card["lane"] == "official_authority" for card in legal["supports"])
    assert "Fictional parent missed exchange" not in store.path.read_text(encoding="utf-8")
    source = store.sentence_source(_document()["document_id"], mapped["map_id"], factual["sentence_id"], "supports", 0)
    assert source["source"]["source_hash"] == "a" * 64


def test_pass73_fails_closed_for_unconfirmed_and_stale_authority(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = SentenceSupportMapStore(root, encryption_key="fictional-test-key")
    try:
        store.create_map({"reviewer_safe_id": "reviewer_001", "selected_authority": _authority(), "user_confirmed": False}, document=_document(), records=_records())
    except Exception as exc:
        assert str(exc) == "sentence_support_confirmation_required"
    else:
        raise AssertionError("mapping must require confirmation")
    stale = store.create_map({"reviewer_safe_id": "reviewer_001", "selected_authority": _authority(freshness="stale"), "user_confirmed": True}, document=_document(), records=_records())
    legal = stale["sentences"][1]
    assert any(card["relationship"] == "stale_authority_requires_review" for card in legal["qualifications"])
    assert "legal_sentence_without_current_exact_authority_match" in legal["missing_context"]


def test_pass73_canonical_api_binds_private_source_to_active_matter(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "fictional-matter-a"
    matter_b = tmp_path / "fictional-matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(
        matter_a,
        title="Fictional sentence map draft",
        content=_document()["content"],
        document_type="draft",
    )
    client = TestClient(api_module.app)
    denied = client.post(
        f"/api/drafting/documents/{document['document_id']}/sentence-support-maps",
        json={"reviewer_safe_id": "reviewer_001", "selected_authority": _authority(), "user_confirmed": False},
    )
    assert denied.status_code == 409
    created = client.post(
        f"/api/drafting/documents/{document['document_id']}/sentence-support-maps",
        json={"reviewer_safe_id": "reviewer_001", "selected_authority": _authority(), "user_confirmed": True},
    )
    assert created.status_code == 200
    mapped = created.json()["map"]
    assert mapped["current_revision_match"] is True and mapped["stale_for_current_draft"] is False
    factual = mapped["sentences"][0]
    source = client.get(
        f"/api/drafting/documents/{document['document_id']}/sentence-support-maps/{mapped['map_id']}/sentences/{factual['sentence_id']}/supports/0/source"
    )
    assert source.status_code == 200
    assert source.json()["source"]["source_hash"] == "a" * 64
    assert len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get(f"/api/drafting/documents/{document['document_id']}/sentence-support-maps/{mapped['map_id']}").status_code == 404


def test_pass73_ships_mirrored_api_and_production_sentence_map_controls() -> None:
    src_api = Path("src/maine_family_law_llm/api.py")
    mirror_api = Path("maine_family_law_llm/api.py")
    src_ui = Path("src/maine_family_law_llm/ui/workbench.js")
    mirror_ui = Path("maine_family_law_llm/ui/workbench.js")
    assert src_api.read_bytes() == mirror_api.read_bytes()
    assert src_ui.read_bytes() == mirror_ui.read_bytes()
    text = src_ui.read_text(encoding="utf-8")
    assert "Sentence-level support map" in text
    assert "/sentence-support-maps" in text
    assert "Map saved draft sentences" in text
