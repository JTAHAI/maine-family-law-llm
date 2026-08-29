from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _rows() -> list[dict[str, object]]:
    return [
        {"evidence_id": "ORIGINAL", "title": "Fictional original", "source_type": "pdf", "source_hash": "a" * 64, "text": "Fictional original text.", "page_number": 1},
        {"evidence_id": "CORRECTED", "title": "Fictional OCR correction", "source_type": "pdf", "source_hash": "b" * 64, "text": "Fictional corrected text.", "page_number": 2},
    ]


def _client(monkeypatch, root: Path, rows: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows)
    return TestClient(api_module.app)


def test_record_lineage_links_active_matter_records_and_drills_to_both_sources(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); rows = _rows(); client = _client(monkeypatch, root, rows)
    create = client.post("/api/evidence/record-lineage/links", json={"link_id": "OCR", "relationship": "ocr_correction", "original_record_id": "ORIGINAL", "derivative_record_id": "CORRECTED", "reviewer_notes": "Fictional reviewer note."})
    assert create.status_code == 200 and create.json()["link"]["review_required"] is True
    assert "does not decide authenticity" in create.json()["link"]["notice"]
    graph = client.get("/api/evidence/record-lineage")
    assert graph.status_code == 200 and graph.json()["relationship_counts"]["ocr_correction"] == 1
    original = client.get("/api/evidence/record-lineage/links/OCR/original/source")
    derivative = client.get("/api/evidence/record-lineage/links/OCR/derivative/source")
    assert original.status_code == derivative.status_code == 200
    assert len(original.json()["source"]["source_token"]) == 64


def test_record_lineage_fails_closed_for_foreign_same_or_changed_source(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); rows = _rows(); client = _client(monkeypatch, root, rows)
    foreign = client.post("/api/evidence/record-lineage/links", json={"link_id": "FOREIGN", "relationship": "changed_copy", "original_record_id": "ORIGINAL", "derivative_record_id": "OTHER-MATTER"})
    same = client.post("/api/evidence/record-lineage/links", json={"link_id": "SAME", "relationship": "changed_copy", "original_record_id": "ORIGINAL", "derivative_record_id": "ORIGINAL"})
    created = client.post("/api/evidence/record-lineage/links", json={"link_id": "COPY", "relationship": "changed_copy", "original_record_id": "ORIGINAL", "derivative_record_id": "CORRECTED"})
    assert foreign.status_code == 400 and foreign.json()["detail"] == "source_record_not_found_in_active_matter"
    assert same.status_code == 400 and same.json()["detail"] == "record_lineage_records_must_differ"
    assert created.status_code == 200
    rows[0] = {**rows[0], "source_hash": "c" * 64}
    changed = client.get("/api/evidence/record-lineage/links/COPY/original/source")
    assert changed.status_code == 400 and changed.json()["detail"] == "record_lineage_source_hash_mismatch"


def test_record_lineage_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    assert "installRecordLineageControl" in src_ui
    assert "/api/evidence/record-lineage/links" in src_ui
    assert "does not decide which text controls" in src_ui
