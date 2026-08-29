from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.child_support_worksheet import ChildSupportWorksheetStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as api_module


def _authority(freshness="current"):
    return {"authority_id": "authority_001", "source_id": "fictional-current-child-support-source", "source_hash": "a" * 64, "citation": "Fictional current child-support source", "title": "Fictional current worksheet", "exact_span": "Fictional exact source span.", "freshness_status": freshness}


def _payload():
    return {"workspace_id": "support_worksheet_001", "reviewer_safe_id": "reviewer_001", "authority_source_id": "fictional-current-child-support-source", "inputs": [{"input_id": "input_001", "field_id": "gross_income", "label": "Gross income", "value": "Fictional reviewer-entered value", "state": "user_entered_unverified"}, {"input_id": "input_002", "field_id": "children", "label": "Children", "value": "", "state": "unknown"}], "missing_facts": ["Fictional missing insurance fact"], "user_confirmed": True}


def test_pass93_encrypted_current_source_preparation_never_calculates(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ChildSupportWorksheetStore(root, encryption_key="fictional-test-key")
    workspace = store.create(_payload(), authority=_authority())
    assert workspace["calculation"] == "not_available" and workspace["worksheet_completion"] == "not_available"
    assert workspace["inputs"][1]["state"] == "unknown"
    assert "Fictional reviewer-entered value" not in store.path.read_text(encoding="utf-8")
    with pytest.raises(IntakeWorkbenchError, match="child_support_current_authority_required"):
        store.create(_payload() | {"workspace_id": "support_worksheet_002"}, authority=_authority("stale"))


def test_pass93_api_scoping_authority_drilldown_and_production_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "inspect_source", lambda _: {"status": "pass", "source_card": {**_authority(), "source_span_preview": "Fictional exact source span."}})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/child-support-worksheets", json=_payload()).status_code == 200
    source = client.get("/api/child-support-worksheets/support_worksheet_001/authority/source")
    assert source.status_code == 200 and source.json()["source"]["lane"] == "official_authority"
    active["root"] = matter_b
    assert client.get("/api/child-support-worksheets/support_worksheet_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Child-support worksheet inputs" in ui and "Save preparation workspace" in ui
