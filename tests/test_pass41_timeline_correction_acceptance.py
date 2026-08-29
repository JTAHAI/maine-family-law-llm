from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "EMAIL-ONE",
            "title": "Fictional first email",
            "source_type": "email",
            "source_hash": "a" * 64,
            "text": "On January 10, 2026, a fictional sender described a scheduling change.",
            "page_number": 1,
        },
        {
            "evidence_id": "EMAIL-TWO",
            "title": "Fictional corrected email",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "On January 11, 2026, a fictional sender clarified the scheduling change.",
            "page_number": 2,
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]] | None = None) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows or _records())
    return TestClient(api_module.app)


def test_timeline_correction_rebinds_only_to_active_matter_records_and_keeps_history(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    created = client.post(
        "/api/timeline/events",
        json={
            "event_label": "Fictional scheduling note",
            "date_value": "2026-01-10",
            "source_record_id": "EMAIL-ONE",
            "source_hash": "a" * 64,
        },
    )
    assert created.status_code == 200
    event_id = created.json()["event"]["event_id"]
    assert created.json()["event"]["source_binding_status"] == "bound_to_active_matter_record"

    updated = client.patch(
        f"/api/timeline/events/{event_id}",
        json={
            "date_value": "2026-01-11",
            "source_record_id": "EMAIL-TWO",
            "reason": "Fictional reviewer corrected the date against the later source.",
        },
    )
    assert updated.status_code == 200
    event = updated.json()["event"]
    assert event["source_record_id"] == "EMAIL-TWO"
    assert event["source_hash"] == "b" * 64
    assert event["correction_history"][-1]["previous"]["source_record_id"] == "EMAIL-ONE"
    assert event["review_required"] is True

    history = client.get(f"/api/timeline/events/{event_id}/history")
    assert history.status_code == 200
    assert history.json()["event"]["source_record_id"] == "EMAIL-TWO"
    assert history.json()["source_drill_down_available"] is True
    assert len(history.json()["history"]) >= 2

    source = client.get(f"/api/timeline/events/{event_id}/source")
    assert source.status_code == 200
    assert source.json()["source"]["record_id"] == "EMAIL-TWO"
    assert len(source.json()["source"]["source_token"]) == 64
    assert source.json()["review_required"] is True


def test_timeline_correction_rejects_foreign_or_hash_mismatched_rebinding(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)
    created = client.post(
        "/api/timeline/events",
        json={"event_label": "Bound event", "source_record_id": "EMAIL-ONE", "source_hash": "a" * 64},
    )
    event_id = created.json()["event"]["event_id"]

    foreign = client.patch(
        f"/api/timeline/events/{event_id}",
        json={"source_record_id": "OTHER-MATTER-RECORD", "reason": "attempted cross-matter rebind"},
    )
    assert foreign.status_code == 400
    assert foreign.json()["detail"] == "source_record_not_found_in_active_matter"

    mismatched = client.patch(
        f"/api/timeline/events/{event_id}",
        json={"source_record_id": "EMAIL-TWO", "source_hash": "a" * 64, "reason": "attempted hash substitution"},
    )
    assert mismatched.status_code == 400
    assert mismatched.json()["detail"] == "source_rebind_hash_mismatch"


def test_timeline_source_drilldown_fails_closed_when_a_record_changes(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    rows = _records()
    client = _client(monkeypatch, case_root, rows)
    created = client.post(
        "/api/timeline/events",
        json={"event_label": "Bound event", "source_record_id": "EMAIL-ONE", "source_hash": "a" * 64},
    )
    event_id = created.json()["event"]["event_id"]

    rows[0]["source_hash"] = "c" * 64
    stale_source = client.get(f"/api/timeline/events/{event_id}/source")
    assert stale_source.status_code == 400
    assert stale_source.json()["detail"] == "event_source_hash_mismatch"


def test_timeline_correction_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    for marker in (
        "installTimelineCorrectionControl",
        "/api/timeline/events/${encodeURIComponent(eventId)}/history",
        "/api/timeline/events/${encodeURIComponent(eventId)}/source",
        "Save review-required correction",
        "append-only",
    ):
        assert marker in src_ui
