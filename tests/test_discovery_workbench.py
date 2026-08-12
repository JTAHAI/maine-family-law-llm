from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.discovery_workbench import DiscoveryWorkbenchStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_discovery_preserves_partial_objection_missing_and_privilege_candidates(
    tmp_path: Path,
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = DiscoveryWorkbenchStore(case, encryption_key="synthetic-test-passphrase")
    store.add_items(
        {
            "items": [
                {
                    "item_id": "request_001",
                    "kind": "interrogatory",
                    "exact_request_text": "Identify synthetic documents.",
                    "source_ref": {"record_id": "discovery_001"},
                    "response_text": "Partial synthetic response.",
                    "privilege_flags": ["attorney_client_candidate"],
                },
                {
                    "item_id": "request_002",
                    "kind": "request_for_production",
                    "exact_request_text": "Produce synthetic records.",
                    "source_ref": {"record_id": "discovery_001"},
                    "objection_text": "Synthetic objection.",
                },
            ]
        }
    )
    store.add_productions(
        {
            "productions": [
                {
                    "production_id": "prod_001",
                    "source_hash": "a" * 64,
                    "request_ids": ["request_001"],
                }
            ]
        }
    )
    gaps = store.gaps()
    assert gaps["objection_only_items"] == ["request_002"]
    assert gaps["items_without_production"] == ["request_002"]
    assert gaps["privilege_candidates"] == ["request_001"]
    assert gaps["compliance"] == "not_determined"
    inventory = store.inventory()
    assert inventory["automatic_service"] is False
    assert inventory["subpoena_issuance"] is False
    assert inventory["privilege_determination"] == "not_determined"


def test_discovery_api_is_matter_scoped_and_does_not_send_service(
    monkeypatch, tmp_path: Path
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    response = client.post(
        "/api/discovery/items",
        json={
            "items": [
                {
                    "item_id": "request_api_001",
                    "kind": "interrogatory",
                    "exact_request_text": "Identify synthetic records.",
                    "source_ref": {"record_id": "discovery_source_001"},
                }
            ]
        },
    )
    assert response.status_code == 200
    inventory = client.get("/api/discovery/inventory").json()
    assert inventory["automatic_service"] is False
    assert inventory["subpoena_issuance"] is False
    assert client.get("/api/discovery/gaps").json()["compliance"] == "not_determined"
    assert len(client.get("/api/discovery/receipt").json()["receipt_hash"]) == 64


def test_discovery_workbench_is_publicly_navigable() -> None:
    html = render_local_workbench_html()
    script = read_workbench_asset("workbench.js")
    assert 'id="discovery-workspace-overlay"' in html
    for label in (
        "Sets and requests",
        "Responses and objections",
        "Privilege/confidentiality review",
        "Exports",
    ):
        assert label in html
    assert 'aria-live="polite"' in html
    assert "open_discovery_workspace" in script
    assert "Nothing is served" in html
