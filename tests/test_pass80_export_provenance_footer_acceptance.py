from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.export_provenance import ExportProvenanceStore
from legal.documents.workspace import create_document, export_text_artifact
from maine_family_law_llm import api as api_module


def _document():
    return {
        "document_id": "a" * 32,
        "current_revision_id": "b" * 32,
        "content": "Fictional legal-review draft text.",
        "source_refs": [{"source_id": "fictional-record-001", "hash": "c" * 64, "page": 1}],
    }


def test_pass80_encrypted_receipt_has_safe_footer_and_completion(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ExportProvenanceStore(root, encryption_key="fictional-test-key")
    prepared = store.start(_document(), product_version="9.0.0", format_name="txt")
    assert "LOCAL EXPORT PROVENANCE" in prepared["footer_text"]
    assert prepared["source_snapshot_sha256"]
    assert str(root) not in prepared["footer_text"]
    assert "Fictional legal-review" not in store.path.read_text(encoding="utf-8")
    completed = store.complete(prepared["receipt_id"], artifact_sha256="d" * 64, size_bytes=123)
    assert completed["status"] == "completed"
    assert completed["review_required"] is True and completed["filing_ready"] is False
    assert store.receipts("a" * 32)["receipts"][0]["artifact_sha256"] == "d" * 64


def test_pass80_text_export_embeds_server_generated_footer(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    document = create_document(root, title="Fictional draft", content="Fictional draft body.")
    footer = "LOCAL EXPORT PROVENANCE — REVIEW REQUIRED\nExport receipt ID: export_fixture"
    path = export_text_artifact(root, document["document_id"], format_name="txt", provenance_footer=footer)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("Export receipt ID: export_fixture\n")
    assert "Fictional draft body." in text


def test_pass80_canonical_export_is_scoped_receipted_and_path_safe(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    document = create_document(
        matter_a,
        title="Fictional export",
        content="Fictional export body.",
        source_refs=[{"source_id": "fictional-record-001", "hash": "e" * 64, "page": 1}],
    )
    client = TestClient(api_module.app)
    export_session = client.post(
        f"/api/document-workspace/documents/{document['document_id']}/export-sessions?format=txt"
    )
    assert export_session.status_code == 200
    response = client.get(export_session.json()["download_url"])
    assert response.status_code == 200
    assert "LOCAL EXPORT PROVENANCE" in response.text
    assert "review-required" in response.text.lower()
    assert str(matter_a) not in response.text
    assert response.headers["x-mfll-export-provenance-receipt"].startswith("export_")
    receipts = client.get(f"/api/document-workspace/documents/{document['document_id']}/export-provenance")
    assert receipts.status_code == 200
    assert receipts.json()["receipts"][-1]["status"] == "completed"
    active["root"] = matter_b
    assert client.get(f"/api/document-workspace/documents/{document['document_id']}/export-provenance").status_code == 404


def test_pass80_mirrored_production_ui_exposes_receipt_state():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "review-required provenance footer" in text
    assert "/export-provenance" in text
