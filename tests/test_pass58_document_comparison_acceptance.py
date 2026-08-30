from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _rows() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "REC_LEFT",
            "title": "Fictional left record",
            "source_hash": "a" * 64,
            "text": "Fictional left wording with a table reference.",
            "source_type": "order",
            "page_count": 2,
            "parser_status": "parsed",
            "ocr_status": "not_needed",
            "parser_metadata": {"table_count": 1, "signature_count": 1},
        },
        {
            "evidence_id": "REC_RIGHT",
            "title": "Fictional right record",
            "source_hash": "b" * 64,
            "text": "Fictional changed wording with a table reference.",
            "source_type": "order",
            "page_count": 3,
            "parser_status": "parsed",
            "ocr_status": "review_required",
            "parser_metadata": {"table_count": 2},
        },
    ]


def _client(monkeypatch, root: Path, rows: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows)
    return TestClient(api_module.app)


def test_document_comparison_is_encrypted_source_bound_and_review_required(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    rows = _rows()
    client = _client(monkeypatch, root, rows)

    created = client.post(
        "/api/evidence/document-comparisons",
        json={"comparison_id": "comparison_001", "left_record_id": "REC_LEFT", "right_record_id": "REC_RIGHT"},
    )
    assert created.status_code == 200
    comparison = created.json()["comparison"]
    assert comparison["review_required"] is True
    assert comparison["text"]["status"] == "changed_requires_review"
    assert comparison["tables"]["status"] == "changed_requires_review"
    assert comparison["signatures"]["status"] == "unavailable_requires_review"
    assert comparison["page_images"]["available"] is False
    assert "does not decide" in comparison["notice"]

    encrypted = root / "19_EVIDENCE_WORK_PRODUCT" / "document-comparisons" / "comparisons.json.enc"
    envelope = json.loads(encrypted.read_text(encoding="utf-8"))
    assert envelope["algorithm"] == "aes-256-gcm"
    assert "Fictional left wording" not in encrypted.read_text(encoding="utf-8")

    listed = client.get("/api/evidence/document-comparisons")
    left_source = client.get("/api/evidence/document-comparisons/comparison_001/source/left")
    right_source = client.get("/api/evidence/document-comparisons/comparison_001/source/right")
    assert listed.status_code == left_source.status_code == right_source.status_code == 200
    assert len(left_source.json()["source"]["source_token"]) == 64
    assert right_source.json()["source"]["source_hash"] == "b" * 64

    rows[0] = {**rows[0], "source_hash": "c" * 64}
    stale = client.get("/api/evidence/document-comparisons/comparison_001/source/left")
    assert stale.status_code == 409
    assert stale.json()["detail"] == "document_comparison_source_hash_mismatch"


def test_document_comparison_fails_closed_for_foreign_or_same_record(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    client = _client(monkeypatch, root, _rows())
    foreign = client.post(
        "/api/evidence/document-comparisons",
        json={"comparison_id": "comparison_002", "left_record_id": "REC_LEFT", "right_record_id": "FOREIGN"},
    )
    same = client.post(
        "/api/evidence/document-comparisons",
        json={"comparison_id": "comparison_003", "left_record_id": "REC_LEFT", "right_record_id": "REC_LEFT"},
    )
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "document_comparison_record_not_found_in_active_matter"
    assert same.status_code == 422
    assert same.json()["detail"] == "document_comparison_records_must_differ"


def test_document_comparison_ui_and_api_assets_are_mirrored() -> None:
    root = Path(__file__).resolve().parents[1]
    source_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    frozen_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    source_api = (root / "src" / "maine_family_law_llm" / "api.py").read_bytes()
    frozen_api = (root / "maine_family_law_llm" / "api.py").read_bytes()
    assert source_ui == frozen_ui
    assert source_api == frozen_api
    assert b"/api/evidence/document-comparisons" in source_ui
    assert b"documentComparisonDelegationBound" in source_ui
    assert b"DocumentComparisonStore" in source_api
