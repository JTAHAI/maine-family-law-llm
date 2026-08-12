from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.docket_reconciliation import DocketReconciliationStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_reconciliation_preserves_docket_only_local_only_and_sealed_warnings(
    tmp_path: Path,
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = DocketReconciliationStore(case, encryption_key="synthetic-test-passphrase")
    store.import_entries(
        {
            "entries": [
                {
                    "entry_id": "docket_001",
                    "sequence": "1",
                    "description": "Synthetic filing",
                    "source_ref": {
                        "record_id": "docket_export_001",
                        "source_hash": "a" * 64,
                        "page": 1,
                    },
                },
                {
                    "entry_id": "docket_002",
                    "description": "Missing attachment",
                    "referenced_attachment": "Attachment A",
                    "source_ref": {"record_id": "docket_export_001", "page": 2},
                },
            ]
        }
    )
    store.add_local_records(
        {
            "records": [
                {"record_id": "filing_001", "title": "Synthetic filing", "source_hash": "a" * 64},
                {"record_id": "private_001", "title": "Unfiled draft", "sealed_confidential": True},
            ]
        }
    )
    result = store.reconcile()
    assert result["decisions"][0]["status"] == "exact_match"
    assert result["decisions"][1]["status"] == "docket_only"
    assert result["local_only_record_ids"] == ["private_001"]
    assert result["sealed_warning"] is True
    assert result["official_record_completeness"] == "not_determined"
    assert len(store.receipt()["receipt_hash"]) == 64


def test_docket_api_is_matter_scoped_and_never_exposes_portal_access(
    monkeypatch, tmp_path: Path
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    response = client.post(
        "/api/docket/import",
        json={
            "entries": [
                {
                    "entry_id": "docket_api_001",
                    "description": "Synthetic docket entry",
                    "source_ref": {"record_id": "docket_export_001"},
                }
            ]
        },
    )
    assert response.status_code == 200
    report = client.get("/api/docket/reconcile").json()
    assert report["official_record_completeness"] == "not_determined"
    assert client.get("/api/docket/inventory").json()["court_portal_access"] is False
    assert len(client.get("/api/docket/receipt").json()["receipt_hash"]) == 64


def test_docket_workbench_is_publicly_navigable() -> None:
    html = render_local_workbench_html()
    script = read_workbench_asset("workbench.js")
    assert 'id="docket-workspace-overlay"' in html
    for label in (
        "Docket import",
        "Missing documents",
        "Sealed/confidential warnings",
        "Export report",
    ):
        assert label in html
    assert 'aria-live="polite"' in html
    assert "open_docket_workspace" in script
    assert "official record complete" in html
