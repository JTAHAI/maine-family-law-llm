from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _rows() -> list[dict[str, object]]:
    return [
        {"evidence_id": "REC_A", "title": "Fictional A", "source_hash": "a" * 64, "text": "fictional source A", "source_type": "note"},
        {"evidence_id": "REC_B", "title": "Fictional B", "source_hash": "b" * 64, "text": "fictional source B", "source_type": "note"},
    ]


def _client(monkeypatch, root: Path, rows: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows)
    return TestClient(api_module.app)


def test_metadata_batch_is_encrypted_audited_and_source_bound(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    rows = _rows()
    client = _client(monkeypatch, root, rows)
    response = client.post(
        "/api/evidence/metadata-review/batches",
        json={
            "batch_id": "metadata_batch_001",
            "record_ids": ["REC_A", "REC_B"],
            "labels": ["reviewed", "fictional"],
            "document_date": "2027-04-01",
            "custodian_safe_id": "custodian_001",
            "confidentiality": "private_record",
            "document_type": "financial_record",
            "reviewer_notes": "Fictional metadata review.",
        },
    )
    assert response.status_code == 200
    batch = response.json()["batch"]
    assert batch["review_required"] is True
    assert batch["update"]["document_type"] == "financial_record"
    assert "never changes the original" in batch["notice"]
    assert len(batch["records"]) == 2

    encrypted = root / "19_EVIDENCE_WORK_PRODUCT" / "metadata-review" / "metadata-review.json.enc"
    envelope = json.loads(encrypted.read_text(encoding="utf-8"))
    assert envelope["algorithm"] == "aes-256-gcm"
    assert "Fictional metadata review" not in encrypted.read_text(encoding="utf-8")

    inventory = client.get("/api/evidence/metadata-review/batches")
    source = client.get("/api/evidence/metadata-review/batches/metadata_batch_001/source/REC_A")
    assert inventory.status_code == source.status_code == 200
    assert len(source.json()["source"]["source_token"]) == 64
    rows[0] = {**rows[0], "source_hash": "c" * 64}
    stale = client.get("/api/evidence/metadata-review/batches/metadata_batch_001/source/REC_A")
    assert stale.status_code == 409
    assert stale.json()["detail"] == "metadata_review_source_hash_mismatch"


def test_metadata_batch_fails_closed_for_unknown_records_and_invalid_metadata(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    client = _client(monkeypatch, root, _rows())
    unknown = client.post("/api/evidence/metadata-review/batches", json={"batch_id": "metadata_batch_002", "record_ids": ["OUTSIDE"], "document_type": "order"})
    bad_date = client.post("/api/evidence/metadata-review/batches", json={"batch_id": "metadata_batch_003", "record_ids": ["REC_A"], "document_date": "2027-99-99"})
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "metadata_review_record_not_found_in_active_matter"
    assert bad_date.status_code == 422
    assert bad_date.json()["detail"] == "metadata_review_document_date_invalid"


def test_metadata_review_production_assets_are_mirrored() -> None:
    root = Path(__file__).resolve().parents[1]
    source_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    source_api = (root / "src" / "maine_family_law_llm" / "api.py").read_bytes()
    mirror_api = (root / "maine_family_law_llm" / "api.py").read_bytes()
    assert source_ui == mirror_ui
    assert source_api == mirror_api
    assert b"/api/evidence/metadata-review/batches" in source_ui
    assert b"MetadataReviewStore" in source_api
