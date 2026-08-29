from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.exhibit_workbench import ExhibitWorkbenchStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as api_module


def _candidate(store: ExhibitWorkbenchStore) -> None:
    store.add_candidates(
        {
            "candidates": [
                {
                    "exhibit_id": "exhibit_001",
                    "original_record_id": "fictional_record_001",
                    "original_hash": "a" * 64,
                    "description": "Fictional source record.",
                    "page_count": 1,
                }
            ]
        }
    )


def _event(event_id: str, event_type: str, **extra: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "exhibit_id": "exhibit_001",
        "event_type": event_type,
        "actor_safe_id": "reviewer_001",
        "occurred_at_claimed": "Fictional claimed time",
        "details": "Fictional user-confirmed custody observation.",
        "user_confirmed": True,
        **extra,
    }


def test_pass69_records_all_custody_event_kinds_with_matter_bound_integrity_receipts(tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    store = ExhibitWorkbenchStore(case_root, encryption_key="fictional-test-key")
    _candidate(store)
    for index, event_type in enumerate(
        ("collection", "transfer", "transformation", "hashing", "review", "export"),
        start=1,
    ):
        extra = {"related_artifact_id": "derivative_001"} if event_type == "transformation" else {}
        recorded = store.record_custody_event(_event(f"custody_{index:03d}", event_type, **extra))
        assert recorded["receipt"]["signature_algorithm"] == "hmac-sha256-local-matter-key"
        assert recorded["source_hash"] == "a" * 64
        assert recorded["authenticity"] == "not_determined"
    verified = store.verify_custody_chain()
    assert verified["event_count"] == 6 and verified["integrity_valid"] is True
    source = store.custody_event_source("custody_006")
    assert source["source"] == {
        "record_id": "fictional_record_001",
        "source_hash": "a" * 64,
        "exhibit_id": "exhibit_001",
    }


def test_pass69_fails_closed_for_unconfirmed_or_tampered_custody_events(tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    store = ExhibitWorkbenchStore(case_root, encryption_key="fictional-test-key")
    _candidate(store)
    with pytest.raises(IntakeWorkbenchError, match="custody_event_confirmation_required"):
        store.record_custody_event(
            {
                "event_id": "custody_001",
                "exhibit_id": "exhibit_001",
                "event_type": "collection",
                "actor_safe_id": "reviewer_001",
            }
        )
    with pytest.raises(IntakeWorkbenchError, match="transformation_artifact_required"):
        store.record_custody_event(_event("custody_002", "transformation"))
    store.record_custody_event(_event("custody_003", "collection"))
    altered = store._load()
    altered["custody_events"][0]["details"] = "Tampered synthetic value."
    store._save(altered)
    assert store.verify_custody_chain()["integrity_valid"] is False


def test_pass69_canonical_api_is_matter_scoped_and_mirrored_ui_has_source_drilldown(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "fictional-matter-a"
    matter_b = tmp_path / "fictional-matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post(
        "/api/exhibits/candidates",
        json={"candidates": [{"exhibit_id": "exhibit_001", "original_record_id": "fictional_record_001", "original_hash": "a" * 64, "page_count": 1}]},
    ).status_code == 200
    event = client.post("/api/exhibits/custody-events", json=_event("custody_001", "collection"))
    assert event.status_code == 200 and event.json()["review_required"] is True
    assert client.get("/api/exhibits/custody-events/verify").json()["integrity_valid"] is True
    source = client.get("/api/exhibits/custody-events/custody_001/source")
    assert source.status_code == 200 and source.json()["source_hash"] == "a" * 64
    active["root"] = matter_b
    assert client.get("/api/exhibits/custody-events/custody_001").status_code == 404
    src = Path("src/maine_family_law_llm/ui/workbench.js")
    assert src.read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = src.read_text(encoding="utf-8")
    assert "Chain-of-custody event capture" in text
    assert "/api/exhibits/custody-events/verify" in text
    assert "Inspect exact source" in text
