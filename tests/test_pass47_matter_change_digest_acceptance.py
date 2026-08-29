from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _rows() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-ONE",
            "title": "Fictional order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "Fictional order record.",
            "page_number": 1,
        },
        {
            "evidence_id": "EMAIL-ONE",
            "title": "Fictional email",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "Fictional parent did not attend the exchange.",
            "page_number": 2,
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows)
    return TestClient(api_module.app)


def test_change_digest_compares_new_records_review_work_and_candidate_contradictions(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    rows = _rows(); client = _client(monkeypatch, case_root, rows)
    checkpoint = client.post("/api/evidence/matter-change-digest/checkpoints", json={"checkpoint_id": "BASELINE", "checkpoint_label": "Fictional review baseline"})
    assert checkpoint.status_code == 200 and checkpoint.json()["checkpoint"]["review_required"] is True
    rows.append({"evidence_id": "NOTICE-ONE", "title": "Fictional notice", "source_type": "notice", "source_hash": "c" * 64, "text": "Fictional hearing notice.", "page_number": 3})
    claim = client.post("/api/evidence/claims", json={"statement": "Fictional parent attend the exchange.", "selected_record_ids": ["EMAIL-ONE"]})
    assert claim.status_code == 200
    digest = client.post("/api/evidence/matter-change-digest/BASELINE/generate")
    assert digest.status_code == 200
    payload = digest.json()["digest"]
    assert payload["new_records"][0]["record_id"] == "NOTICE-ONE"
    assert payload["new_candidate_contradictions"]
    assert any(row["section"] == "claims" for row in payload["review_section_changes"])
    assert "does not identify altered conclusions" in payload["notice"]
    source = client.get("/api/evidence/matter-change-digest/BASELINE/records/NOTICE-ONE/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64


def test_change_digest_fails_closed_for_duplicate_or_unknown_checkpoint_and_unknown_record(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    rows = _rows(); client = _client(monkeypatch, case_root, rows)
    first = client.post("/api/evidence/matter-change-digest/checkpoints", json={"checkpoint_id": "BASELINE", "checkpoint_label": "Fictional review baseline"})
    duplicate = client.post("/api/evidence/matter-change-digest/checkpoints", json={"checkpoint_id": "BASELINE", "checkpoint_label": "Duplicate"})
    unknown = client.post("/api/evidence/matter-change-digest/UNKNOWN/generate")
    missing_record = client.get("/api/evidence/matter-change-digest/BASELINE/records/OTHER-MATTER/source")
    assert first.status_code == 200
    assert duplicate.status_code == 400 and duplicate.json()["detail"] == "change_digest_checkpoint_id_exists"
    assert unknown.status_code == 400 and unknown.json()["detail"] == "change_digest_checkpoint_not_found"
    assert missing_record.status_code == 400 and missing_record.json()["detail"] == "change_digest_record_not_found"


def test_change_digest_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    assert "installMatterChangeDigestControl" in src_ui
    assert "/api/evidence/matter-change-digest" in src_ui
    assert "does not resolve contradictions, calculate deadlines, or approve work" in src_ui
