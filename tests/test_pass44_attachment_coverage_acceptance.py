from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "EMAIL-ONE",
            "title": "Fictional email",
            "source_type": "email",
            "source_hash": "a" * 64,
            "text": "The fictional sender referenced an attached bank receipt.",
            "page_number": 1,
        },
        {
            "evidence_id": "RECEIPT-ONE",
            "title": "Fictional receipt",
            "source_type": "pdf",
            "source_hash": "b" * 64,
            "text": "Fictional bank receipt for review only.",
            "page_number": 2,
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]] | None = None) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows or _records())
    return TestClient(api_module.app)


def test_attachment_coverage_preserves_explicit_scoped_states_and_source_drilldown(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    created = client.post(
        "/api/evidence/attachment-coverage",
        json={
            "attachment_id": "ATTACHMENT-ONE",
            "attachment_label": "Fictional bank receipt",
            "coverage_state": "referenced",
            "source_record_id": "EMAIL-ONE",
            "source_hash": "a" * 64,
        },
    )
    assert created.status_code == 200
    item = created.json()["attachment"]
    assert item["coverage_state"] == "referenced"
    assert item["coverage_scope"] == "selected_active_matter_records_only"
    assert item["source_hash"] == "a" * 64
    assert item["review_required"] is True

    reviewed = client.post(
        "/api/evidence/attachment-coverage/ATTACHMENT-ONE/review",
        json={
            "coverage_state": "absent_in_selected_scope",
            "reviewer_notes": "Fictional reviewer did not locate the receipt in the selected local records.",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["attachment"]["coverage_state"] == "absent_in_selected_scope"
    assert reviewed.json()["attachment"]["review_required"] is True

    listed = client.get("/api/evidence/attachment-coverage")
    assert listed.status_code == 200
    assert listed.json()["state_counts"]["absent_in_selected_scope"] == 1
    assert "does not exist elsewhere" in listed.json()["notice"]

    source = client.get("/api/evidence/attachment-coverage/ATTACHMENT-ONE/source")
    assert source.status_code == 200
    assert source.json()["source"]["record_id"] == "EMAIL-ONE"
    assert len(source.json()["source"]["source_token"]) == 64


def test_attachment_coverage_rejects_unbound_or_incomplete_located_state(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    foreign = client.post(
        "/api/evidence/attachment-coverage",
        json={
            "attachment_id": "ATTACHMENT-FOREIGN",
            "attachment_label": "Fictional attachment",
            "source_record_id": "OTHER-MATTER-RECORD",
        },
    )
    assert foreign.status_code == 400
    assert foreign.json()["detail"] == "source_record_not_found_in_active_matter"

    created = client.post(
        "/api/evidence/attachment-coverage",
        json={
            "attachment_id": "ATTACHMENT-ONE",
            "attachment_label": "Fictional bank receipt",
            "source_record_id": "EMAIL-ONE",
        },
    )
    assert created.status_code == 200
    incomplete = client.post(
        "/api/evidence/attachment-coverage/ATTACHMENT-ONE/review",
        json={"coverage_state": "located", "reviewer_notes": "attempted location without a record"},
    )
    assert incomplete.status_code == 400
    assert incomplete.json()["detail"] == "located_attachment_record_required"


def test_attachment_source_drilldown_fails_closed_after_source_hash_changes(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    rows = _records()
    client = _client(monkeypatch, case_root, rows)
    created = client.post(
        "/api/evidence/attachment-coverage",
        json={"attachment_id": "ATTACHMENT-ONE", "attachment_label": "Fictional receipt", "source_record_id": "EMAIL-ONE"},
    )
    assert created.status_code == 200
    rows[0]["source_hash"] = "c" * 64
    source = client.get("/api/evidence/attachment-coverage/ATTACHMENT-ONE/source")
    assert source.status_code == 400
    assert source.json()["detail"] == "attachment_source_hash_mismatch"


def test_attachment_coverage_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    for marker in (
        "installAttachmentCoverageControl",
        "Absent in selected scope",
        "/api/evidence/attachment-coverage",
        "Inspect source record",
        "does not exist elsewhere",
    ):
        assert marker in src_ui
