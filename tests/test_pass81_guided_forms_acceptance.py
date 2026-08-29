from pathlib import Path

from fastapi.testclient import TestClient

from legal.documents.workspace import commit_revision, create_document, propose_revision
from legal.forms.session_store import GuidedFormSessionStore
from maine_family_law_llm import api as api_module


def _forms():
    return [
        {
            "source_id": "form-fm-001",
            "form_id": "FM-001",
            "title": "Fictional current form",
            "citation": "FM-001",
            "source_class": "court_form",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
            "version_date": "07/2026",
            "text": "Plaintiff: Defendant: Signature: Date:",
        },
        {
            "source_id": "form-fm-999",
            "form_id": "FM-999",
            "title": "Fictional stale form",
            "citation": "FM-999",
            "source_class": "court_form",
            "authority_status": "verified_official_maine",
            "freshness_status": "stale",
            "version_date": "01/2020",
            "text": "Plaintiff: Signature:",
        },
    ]


def test_pass81_guided_session_values_are_encrypted_and_audit_linked(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = GuidedFormSessionStore(root, encryption_key="fictional-test-key")
    session = store.create({
        "session_id": "a" * 24,
        "document_id": "b" * 32,
        "build_id": "c" * 24,
        "form_values": {"FM-001": {"plaintiff_name": "Alex Fiction"}},
        "reviewer_notes": "Fictional working-copy note.",
    })
    assert session["review_required"] is True and session["filing_ready"] is False
    encrypted = store.path.read_text(encoding="utf-8")
    assert "Alex Fiction" not in encrypted and "Fictional working-copy" not in encrypted
    session["completion_id"] = "d" * 24
    updated = store.replace(session, action="record_guided_form_completion")
    assert updated["completion_id"] == "d" * 24
    assert len(store._load()["ledger"]) == 2


def test_pass81_session_persists_validates_stale_forms_and_fails_closed(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: [])
    monkeypatch.setattr(api_module.AuthorityProductService, "list_forms", lambda self, **kwargs: {"status": "pass", "build_id": "f" * 24, "forms": _forms()})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(matter_a, title="Fictional form draft", content="FM-001.", document_type="draft")
    client = TestClient(api_module.app)
    created = client.post("/api/forms/session", json={"document_id": document["document_id"], "selected_form_ids": ["FM-001"], "approved": True})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    patched = client.patch(f"/api/forms/session/{session_id}", json={"form_values": {"FM-001": {"plaintiff_name": "Alex Fiction"}}, "reviewer_notes": "Fictional local note.", "approved": True})
    assert patched.status_code == 200 and patched.json()["session"]["form_values"]["FM-001"]["plaintiff_name"] == "Alex Fiction"
    encrypted_path = matter_a / "19_DRAFTING" / "guided-form-sessions" / "sessions.json.enc"
    assert "Alex Fiction" not in encrypted_path.read_text(encoding="utf-8")
    validated = client.post(f"/api/forms/session/{session_id}/validate", json={"confirmed": True})
    assert validated.status_code == 200 and validated.json()["filing_ready"] is False
    stale = client.post("/api/forms/session", json={"document_id": document["document_id"], "selected_form_ids": ["FM-999"], "approved": True})
    assert stale.status_code == 200
    assert "form_not_verified_current:FM-999" in stale.json()["blockers"]
    active["root"] = matter_b
    assert client.get(f"/api/forms/session/{session_id}").status_code == 404


def test_pass81_session_validation_rejects_changed_document_revision(monkeypatch, tmp_path: Path):
    root = tmp_path / "matter"
    root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: [])
    monkeypatch.setattr(api_module.AuthorityProductService, "list_forms", lambda self, **kwargs: {"status": "pass", "build_id": "f" * 24, "forms": _forms()})
    document = create_document(root, title="Fictional form draft", content="FM-001.", document_type="draft")
    client = TestClient(api_module.app)
    created = client.post("/api/forms/session", json={"document_id": document["document_id"], "selected_form_ids": ["FM-001"], "approved": True})
    session_id = created.json()["session_id"]
    proposal = propose_revision(root, document["document_id"], content="Changed FM-001.", base_revision_id=document["current_revision_id"])
    commit_revision(root, document["document_id"], revision_id=proposal["revision_id"], confirmation_token=proposal["confirmation_token"], confirmed=True)
    rejected = client.post(f"/api/forms/session/{session_id}/validate", json={"confirmed": True})
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "review_build_stale"


def test_pass81_production_ui_assets_are_mirrored_and_source_drillable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.css").read_bytes() == Path("maine_family_law_llm/ui/workbench.css").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Guided form session" in text
    assert "/api/forms/session" in text
    assert "Open exact official form source" in text
