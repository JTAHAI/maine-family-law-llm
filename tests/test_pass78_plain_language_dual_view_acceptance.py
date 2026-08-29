from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.dual_view import DualViewStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module


def _document():
    return {
        "document_id": "f" * 32,
        "current_revision_id": "e" * 32,
        "content": "Fictional legal-review draft with a source-bound statement.",
        "source_refs": [{"source_id": "fictional-record-001", "hash": "a" * 64, "page": 1}],
    }


def _payload():
    return {
        "view_id": "plain_view_001",
        "reviewer_safe_id": "reviewer_001",
        "plain_language_text": "Fictional plain-language working copy for reviewer discussion.",
        "user_confirmed": True,
    }


def test_pass78_encrypted_revision_and_source_bound_view(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = DualViewStore(root, encryption_key="fictional-test-key")
    created = store.create(_payload(), _document())
    assert created["revision_id"] == "e" * 32
    assert created["source_ref_count"] == 1
    assert created["source_refs_sha256"]
    assert created["review_required"] is True
    assert created["filing_ready"] is False
    encrypted = store.path.read_text(encoding="utf-8")
    assert "Fictional plain-language" not in encrypted
    assert "Fictional legal-review" not in encrypted
    current = store.get("f" * 32, "plain_view_001", "e" * 32)
    stale = store.get("f" * 32, "plain_view_001", "d" * 32)
    assert current["current_revision_match"] is True
    assert stale["stale_for_current_document"] is True


def test_pass78_canonical_api_matter_scope_and_confirmation(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(
        matter_a,
        title="Fictional draft",
        content="Fictional legal-review draft.",
        document_type="draft",
        source_refs=[{"source_id": "fictional-record-001", "hash": "b" * 64, "page": 1}],
    )
    client = TestClient(api_module.app)
    missing_confirmation = _payload() | {"user_confirmed": False}
    assert client.post(f"/api/drafting/documents/{document['document_id']}/dual-views", json=missing_confirmation).status_code == 409
    created = client.post(f"/api/drafting/documents/{document['document_id']}/dual-views", json=_payload())
    assert created.status_code == 200
    assert created.json()["view"]["source_ref_count"] == 1
    loaded = client.get(f"/api/drafting/documents/{document['document_id']}/dual-views/plain_view_001")
    assert loaded.status_code == 200
    assert loaded.json()["view"]["current_revision_match"] is True
    active["root"] = matter_b
    assert client.get(f"/api/drafting/documents/{document['document_id']}/dual-views/plain_view_001").status_code == 404


def test_pass78_production_assets_are_mirrored_and_expose_action():
    source_api = Path("src/maine_family_law_llm/api.py")
    mirror_api = Path("maine_family_law_llm/api.py")
    source_ui = Path("src/maine_family_law_llm/ui/workbench.js")
    mirror_ui = Path("maine_family_law_llm/ui/workbench.js")
    assert source_api.read_bytes() == mirror_api.read_bytes()
    assert source_ui.read_bytes() == mirror_ui.read_bytes()
    text = source_ui.read_text(encoding="utf-8")
    assert "Plain-language dual view" in text
    assert "Create linked view" in text
    assert "Open linked source" in text
    assert "/dual-views" in text
