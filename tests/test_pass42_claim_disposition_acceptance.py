from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-ONE",
            "title": "Fictional order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "The fictional order states that payment is due on January 10, 2026.",
            "page_number": 1,
        },
        {
            "evidence_id": "EMAIL-ONE",
            "title": "Fictional communication",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "The fictional sender states payment was not made on January 10, 2026. However, payment was delayed because the bank processed the transfer later.",
            "page_number": 2,
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]] | None = None) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows or _records())
    return TestClient(api_module.app)


def test_claim_disposition_creates_source_bound_cards_and_records_review(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    created = client.post(
        "/api/evidence/claims",
        json={
            "statement": "Payment was not made on January 10, 2026.",
            "selected_record_ids": ["ORDER-ONE", "EMAIL-ONE"],
            "claim_type": "factual_claim",
        },
    )
    assert created.status_code == 200
    claim = created.json()["claim"]
    claim_id = claim["claim_id"]
    assert claim["supports"]
    assert claim["contradicts"]
    assert claim["qualifies"]
    assert claim["automated_disposition"] == "contradicted_or_disputed_review_required"
    assert claim["review_required"] is True

    card_source = client.get(f"/api/evidence/claims/{claim_id}/cards/supports/0/source")
    assert card_source.status_code == 200
    assert card_source.json()["source"]["record_id"] == claim["supports"][0]["record_id"]
    assert len(card_source.json()["source"]["source_token"]) == 64
    assert card_source.json()["review_required"] is True

    reviewed = client.post(
        f"/api/evidence/claims/{claim_id}/review",
        json={
            "reviewer_status": "accepted_with_qualification",
            "reviewer_notes": "Fictional reviewer recorded the qualification for follow-up.",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["claim"]["reviewer_status"] == "accepted_with_qualification"
    assert reviewed.json()["claim"]["review_required"] is True

    fetched = client.get(f"/api/evidence/claims/{claim_id}")
    assert fetched.status_code == 200
    assert len(fetched.json()["history"]) >= 2


def test_claim_disposition_fails_closed_for_missing_or_foreign_sources_and_invalid_decision(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    missing_source = client.post("/api/evidence/claims", json={"statement": "A fictional claim"})
    assert missing_source.status_code == 400
    assert missing_source.json()["detail"] == "claim_source_record_required"

    foreign_source = client.post(
        "/api/evidence/claims",
        json={"statement": "A fictional claim", "selected_record_ids": ["OTHER-MATTER-RECORD"]},
    )
    assert foreign_source.status_code == 400
    assert foreign_source.json()["detail"] == "claim_source_record_not_found_in_active_matter"

    created = client.post(
        "/api/evidence/claims",
        json={"statement": "Payment was not made", "selected_record_ids": ["EMAIL-ONE"]},
    )
    claim_id = created.json()["claim"]["claim_id"]
    invalid = client.post(
        f"/api/evidence/claims/{claim_id}/review",
        json={"reviewer_status": "filing_ready", "reviewer_notes": "attempted bypass"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "claim_reviewer_status_invalid"


def test_claim_source_drilldown_fails_closed_when_bound_record_hash_changes(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    rows = _records()
    client = _client(monkeypatch, case_root, rows)
    created = client.post(
        "/api/evidence/claims",
        json={"statement": "Payment was not made", "selected_record_ids": ["EMAIL-ONE"]},
    )
    claim_id = created.json()["claim"]["claim_id"]
    rows[1]["source_hash"] = "c" * 64
    source = client.get(f"/api/evidence/claims/{claim_id}/cards/contradicts/0/source")
    assert source.status_code == 400
    assert source.json()["detail"] == "claim_source_hash_mismatch"


def test_claim_disposition_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    for marker in (
        "installClaimDispositionControl",
        "Create source-bound review",
        "/api/evidence/claims/${encodeURIComponent(claimId)}/cards/",
        "Record reviewer decision",
        "Inspect exact source",
    ):
        assert marker in src_ui
