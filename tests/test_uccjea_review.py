from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.uccjea_review import UccjeaReviewStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_overlap_masking_and_no_jurisdiction_conclusion(tmp_path: Path) -> None:
    c = tmp_path / "synthetic"
    c.mkdir()
    s = UccjeaReviewStore(c, encryption_key="synthetic-test-passphrase")
    s.connections(
        {
            "connections": [
                {
                    "connection_id": "connection_001",
                    "child_id": "child_001",
                    "state_territory_country": "Maine",
                    "date_start": "2026-01-01",
                    "date_end": "2026-02-01",
                    "source_ref": {"record_id": "record_001"},
                },
                {
                    "connection_id": "connection_002",
                    "child_id": "child_001",
                    "state_territory_country": "Vermont",
                    "date_start": "2026-01-15",
                    "date_end": "2026-02-15",
                    "source_ref": {"record_id": "record_002"},
                },
            ]
        }
    )
    assert s.inventory()["exact_addresses_exposed"] is False
    assert s.factors()["conflicts"]
    assert s.factors()["jurisdiction_conclusion"] == "not_determined"


def test_uccjea_api_is_retained_but_ui_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    c = tmp_path / "synthetic"
    c.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: c)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    x = TestClient(api_module.app)
    assert (
        x.post(
            "/api/uccjea/connections",
            json={
                "connections": [
                    {
                        "connection_id": "connection_api_001",
                        "child_id": "child_api_001",
                        "state_territory_country": "Maine",
                        "source_ref": {"record_id": "record_api_001"},
                    }
                ]
            },
        ).status_code
        == 200
    )
    assert len(x.get("/api/uccjea/receipt").json()["receipt_hash"]) == 64
    h, j = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert 'id="uccjea-workspace-overlay"' in h
    assert "State map" in h
    assert "open_uccjea_workspace" in j
