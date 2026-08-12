from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def test_care_safety_and_parenting_schedule_have_meaningful_api_actions(
    monkeypatch, tmp_path: Path
) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-acceptance-passphrase")
    client = TestClient(api_module.app)

    care = client.post(
        "/api/care-pathways",
        json={"pathways": [{"pathway_id": "pathway_one", "child_id": "child_one", "kind": "guardianship", "source_ref": {"record_id": "record_one"}}]},
    )
    safety = client.post(
        "/api/safety/records",
        json={"records": [{"record_id": "safety_one", "kind": "order_candidate", "summary": "Fictional source-bound safety summary.", "source_ref": {"record_id": "record_two"}}]},
    )
    schedule = client.post(
        "/api/parenting-schedule/terms",
        json={"terms": [{"term_id": "term_one", "topic": "holiday", "exact_language": "Fictional exact schedule language.", "source_ref": {"record_id": "record_three"}}]},
    )
    for response in (care, safety, schedule):
        assert response.status_code == 200, response.text
        assert response.json()["review_required"] is True
        assert response.json()["local_only"] is True

    scenario = client.post(
        "/api/parenting-schedule/scenarios",
        json={"scenario_id": "scenario_one", "term_ids": ["term_one"], "events": [{"label": "Fictional holiday", "date_candidate": "2027-01-01"}]},
    )
    assert scenario.status_code == 200
    assert scenario.json()["calendar_write"] is False
    assert client.get("/api/care-pathways/gaps").json()["review_required"] is True
    for route in ("/api/care-pathways/receipt", "/api/safety/receipt", "/api/parenting-schedule/receipt"):
        receipt = client.get(route)
        assert receipt.status_code == 200
        assert len(receipt.json()["receipt_hash"]) == 64


def test_care_safety_and_schedule_are_real_production_ui_workspaces() -> None:
    html = render_local_workbench_html()
    javascript = read_workbench_asset("workbench.js")
    for workspace_id in ("care-workspace-overlay", "safety-workspace-overlay", "schedule-workspace-overlay"):
        assert f'id="{workspace_id}"' in html
    for marker in (
        "addCare", "addSafety", "addSchedule", "showCareReceipt", "showSafetyReceipt",
        "showScheduleReceipt", "installSpecializedSourceInspectors", "Inspect exact source",
    ):
        assert marker in javascript
