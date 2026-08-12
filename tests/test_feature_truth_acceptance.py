from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import (
    EXPERIMENTAL_DISABLED_FEATURE_IDS,
    app,
    capability_inventory,
)
from maine_family_law_llm.local_workbench_ui import read_workbench_asset
from maine_family_law_llm.production_ui import production_ui_manifest


SLICE_PATHS = (
    "/api/intake/matters",
    "/api/orders/inventory",
    "/api/calendar/events",
    "/api/docket/inventory",
    "/api/discovery/inventory",
    "/api/exhibits/inventory",
    "/api/statements/inventory",
    "/api/hearings/inventory",
    "/api/appellate/inventory",
    "/api/uccjea/inventory",
    "/api/icwa/inventory",
)

PUBLIC_COMMAND_IDS = (
    "open_matter_intake",
    "open_orders_workspace",
    "open_calendar_workspace",
    "open_docket_workspace",
    "open_discovery_workspace",
    "open_exhibits_workspace",
    "open_statements_workspace",
    "open_hearing_workspace",
    "open_appellate_workspace",
    "open_uccjea_workspace",
    "open_icwa_workspace",
)


def test_unaccepted_slices_fail_closed_in_production(monkeypatch) -> None:
    monkeypatch.delenv("MFL_ENABLE_EXPERIMENTAL_SLICES_21_31", raising=False)
    with TestClient(app) as client:
        for path in SLICE_PATHS:
            response = client.get(path)
            assert response.status_code == 404, path
            assert response.json() == {
                "detail": "feature_not_in_release_scope",
                "status": "experimental_disabled",
                "review_required": True,
            }
            assert response.headers["x-mfl-release-scope"] == "experimental-disabled"
            assert response.headers["cache-control"] == "no-store"

        existing_intake = client.post("/api/intake/understand", json={})
        assert existing_intake.headers.get("x-mfl-release-scope") != "experimental-disabled"
        assert existing_intake.json().get("detail") != "feature_not_in_release_scope"


def test_unaccepted_slices_have_no_production_navigation_entry() -> None:
    javascript = read_workbench_asset("workbench.js")
    for command_id in PUBLIC_COMMAND_IDS:
        assert f"id: '{command_id}'" not in javascript
        assert f"id:'{command_id}'" not in javascript


def test_runtime_manifest_cannot_generate_store_claims_for_unaccepted_slices() -> None:
    release_scope = capability_inventory()["release_scope"]
    assert release_scope["accepted_feature_ids"] == []
    assert release_scope["experimental_disabled_feature_ids"] == list(
        EXPERIMENTAL_DISABLED_FEATURE_IDS
    )
    assert release_scope["experimental_backend_override_enabled"] is False
    assert release_scope["store_feature_claim_eligible"] is False

    ui_manifest = production_ui_manifest()
    assert all(
        workspace_id not in ui_manifest["workspace_ids"]
        for workspace_id in ui_manifest["experimental_hidden_workspace_ids"]
    )
    assert all(
        path not in ui_manifest["api_paths"]
        for path in ui_manifest["experimental_hidden_api_paths"]
    )


def test_feature_truth_artifacts_contain_no_private_paths_or_people() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "dist" / "ga_today" / "evidence" / "02_feature_truth_manifest.json"
    documentation_path = root / "docs" / "GA_TODAY_FEATURE_TRUTH.md"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["acceptance_summary"]["accepted_feature_ids"] == []
    assert len(manifest["features"]) == 11
    assert {feature["status"] for feature in manifest["features"]} == {"hidden"}
    combined = manifest_path.read_text(encoding="utf-8") + documentation_path.read_text(
        encoding="utf-8"
    )
    for forbidden in ("C:\\Users\\", "D:\\dev\\", "justi", "@example.com"):
        assert forbidden not in combined
