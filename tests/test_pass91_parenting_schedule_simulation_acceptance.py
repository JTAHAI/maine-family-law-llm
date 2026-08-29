from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.parenting_schedule import ParentingScheduleStore
from maine_family_law_llm import api as api_module


def _records():
    return [
        {"evidence_id": "SCHEDULE-001", "source_hash": "a" * 64, "title": "Fictional parenting record"},
        {"evidence_id": "SCHOOL-001", "source_hash": "b" * 64, "title": "Fictional school record"},
    ]


def _payload():
    return {
        "simulation_id": "simulation_001",
        "reviewer_safe_id": "reviewer_001",
        "user_confirmed": True,
        "scenarios": [
            {
                "scenario_id": "scenario_a",
                "label": "Fictional calendar A",
                "events": [
                    {"date_candidate": "2026-07-04", "label": "Holiday", "category": "holiday", "source_ref": {"record_id": "SCHEDULE-001", "source_hash": "a" * 64}},
                    {"date_candidate": "2026-07-05", "label": "Travel", "category": "travel", "source_ref": {"record_id": "SCHEDULE-001", "source_hash": "a" * 64}},
                    {"date_candidate": "2026-07-06", "label": "Exchange", "category": "exchange", "source_ref": {"record_id": "SCHEDULE-001", "source_hash": "a" * 64}},
                ],
            },
            {
                "scenario_id": "scenario_b",
                "label": "Fictional calendar B",
                "events": [
                    {"date_candidate": "2026-07-04", "label": "School day", "category": "school", "source_ref": {"record_id": "SCHOOL-001", "source_hash": "b" * 64}},
                    {"date_candidate": "2026-07-07", "label": "Parenting time", "category": "parenting_time", "source_ref": {"record_id": "SCHEDULE-001", "source_hash": "a" * 64}},
                ],
            },
        ],
    }


def test_pass91_encrypted_neutral_schedule_comparison(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ParentingScheduleStore(root, encryption_key="fictional-test-key")
    result = store.simulate_v2(_payload(), records=_records())
    categories = {event["category"] for scenario in result["scenarios"] for event in scenario["events"]}
    assert {"parenting_time", "travel", "holiday", "school", "exchange"} <= categories
    assert result["recommendation"] == "not_available"
    assert result["filing_ready"] is False
    assert result["date_overlaps"] == [{"date_candidate": "2026-07-04", "scenario_ids": ["scenario_a", "scenario_b"], "status": "review_required"}]
    assert store.simulation_v2_source("simulation_001", "SCHOOL-001")["source"]["source_hash"] == "b" * 64
    assert "Fictional calendar A" not in store.path.read_text(encoding="utf-8")
    bad = _payload()
    bad["simulation_id"] = "simulation_002"
    bad["scenarios"][0]["events"][0]["category"] = "custody_recommendation"
    with pytest.raises(IntakeWorkbenchError, match="schedule_simulation_category_invalid"):
        store.simulate_v2(bad, records=_records())


def test_pass91_api_scope_source_drilldown_and_shipped_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _: _records())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/parenting-schedule/simulations-v2", json=_payload()).status_code == 200
    source = client.get("/api/parenting-schedule/simulations-v2/simulation_001/sources/SCHOOL-001")
    assert source.status_code == 200
    assert len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get("/api/parenting-schedule/simulations-v2/simulation_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Parenting schedule simulation" in ui and "Open exact source record" in ui
