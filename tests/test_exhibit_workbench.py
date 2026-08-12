from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.exhibit_workbench import ExhibitWorkbenchStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def _store(tmp_path: Path) -> ExhibitWorkbenchStore:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    return ExhibitWorkbenchStore(case, encryption_key="synthetic-test-passphrase")


def _candidate(store: ExhibitWorkbenchStore, exhibit_id: str = "exhibit_001") -> None:
    store.add_candidates(
        {
            "candidates": [
                {
                    "exhibit_id": exhibit_id,
                    "original_record_id": "record_001",
                    "original_hash": "a" * 64,
                    "proposed_label": "Exhibit A",
                    "description": "Synthetic record.",
                    "page_count": 3,
                }
            ]
        }
    )


def test_numbering_creates_hash_bound_derivative_without_changing_original(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _candidate(store)
    store.review_label(
        {
            "exhibit_id": "exhibit_001",
            "approved_label": "Exhibit A",
            "reviewer_safe_id": "reviewer_001",
        }
    )
    derivative = store.create_numbering(
        {
            "exhibit_id": "exhibit_001",
            "prefix": "EX",
            "start": 1,
            "reviewer_safe_id": "reviewer_001",
        }
    )
    assert derivative["source_hash"] == "a" * 64
    assert derivative["settings"]["original_modified"] is False
    assert derivative["page_mapping"][2]["control_number"] == "EX3"
    with pytest.raises(IntakeWorkbenchError, match="conflicting_number_range"):
        store.create_numbering(
            {
                "exhibit_id": "exhibit_001",
                "prefix": "EX",
                "start": 3,
                "reviewer_safe_id": "reviewer_001",
            }
        )


def test_binder_page_mapping_manifest_and_safety_limitations(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _candidate(store)
    store.review_label(
        {
            "exhibit_id": "exhibit_001",
            "approved_label": "Exhibit A",
            "reviewer_safe_id": "reviewer_001",
        }
    )
    binder = store.create_binder(
        {
            "binder_id": "binder_001",
            "exhibit_ids": ["exhibit_001"],
            "reviewer_safe_id": "reviewer_001",
        }
    )
    manifest = store.manifest("binder_001")
    assert binder["includes_originals_by_default"] is False
    assert manifest["page_mapping"][0]["binder_start_page"] == 2
    assert manifest["authenticity"] == "not_determined"
    assert len(store.receipt()["ledger_hash"]) == 64


def test_exhibit_api_is_retained_but_workspace_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    response = client.post(
        "/api/exhibits/candidates",
        json={
            "candidates": [
                {
                    "exhibit_id": "exhibit_api_001",
                    "original_record_id": "record_api_001",
                    "original_hash": "b" * 64,
                    "page_count": 1,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert client.get("/api/exhibits/inventory").json()["originals_immutable"] is True
    assert len(client.get("/api/exhibits/receipt").json()["receipt_hash"]) == 64
    html, script = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert 'id="exhibits-workspace-overlay"' in html
    assert "Bates/control numbering" in html and "Provenance ledger" in html
    assert "open_exhibits_workspace" in script
