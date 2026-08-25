from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import ACCEPTED_FEATURE_IDS, app, capability_inventory
from maine_family_law_llm.local_workbench_ui import read_workbench_asset
from maine_family_law_llm.production_ui import production_ui_manifest


SLICE_PATHS = (
    "/api/intake/matters", "/api/orders/inventory", "/api/calendar/events",
    "/api/docket/inventory", "/api/discovery/inventory", "/api/exhibits/inventory",
    "/api/statements/inventory", "/api/hearings/inventory", "/api/appellate/inventory",
    "/api/uccjea/inventory", "/api/icwa/inventory", "/api/care-pathways/inventory",
    "/api/safety/inventory", "/api/parenting-schedule/inventory", "/api/negotiation/inventory",
    "/api/property/inventory", "/api/modification/inventory", "/api/foaa/inventory",
    "/api/filing-readiness/inventory", "/api/image-evidence/inventory",
    "/api/email-integrity/inventory", "/api/reviewer-handoff/inventory",
    "/api/language-access/inventory", "/api/resources/inventory",
)

PUBLIC_COMMAND_IDS = (
    "open_matter_intake", "open_orders_workspace", "open_calendar_workspace",
    "open_docket_workspace", "open_discovery_workspace", "open_exhibits_workspace",
    "open_statements_workspace", "open_hearing_workspace", "open_appellate_workspace",
    "open_uccjea_workspace", "open_icwa_workspace", "open_care_workspace",
    "open_safety_workspace", "open_schedule_workspace", "open_negotiation_workspace",
    "open_property_workspace", "open_modification_workspace", "open_foaa_workspace",
    "open_filing_workspace", "open_image_evidence_workspace",
    "open_email_integrity_workspace", "open_handoff_workspace", "open_language_workspace",
    "open_resource_workspace",
)


def test_accepted_specialized_routes_are_not_release_gated() -> None:
    with TestClient(app) as client:
        for path in SLICE_PATHS:
            response = client.get(path)
            assert response.headers.get("x-mfl-release-scope") != "experimental-disabled", path
            assert response.json().get("detail") != "feature_not_in_release_scope", path
            assert response.headers.get("x-mfll-audit-event-id"), path
            assert response.headers.get("x-mfll-rbac") == "local-desktop-reviewer", path


def test_every_accepted_specialized_workbench_has_production_navigation() -> None:
    javascript = read_workbench_asset("workbench.js")
    for command_id in PUBLIC_COMMAND_IDS:
        assert f"id:'{command_id}'" in javascript or f"id: '{command_id}'" in javascript
    assert javascript.count("group:'Specialized workbenches'") == 24
    assert "openSpecializedSourceRecord" in javascript
    assert "Review required" in javascript


def test_runtime_and_ui_manifests_publish_only_the_accepted_scope() -> None:
    release_scope = capability_inventory()["release_scope"]
    assert len(ACCEPTED_FEATURE_IDS) == 54
    assert release_scope["accepted_feature_ids"] == list(ACCEPTED_FEATURE_IDS)
    assert release_scope["experimental_disabled_feature_ids"] == []
    assert release_scope["experimental_backend_override_enabled"] is False
    assert release_scope["store_feature_claim_eligible"] is True

    ui_manifest = production_ui_manifest()
    assert ui_manifest["status"] == "pass"
    assert ui_manifest["experimental_hidden_workspace_ids"] == []
    assert ui_manifest["experimental_hidden_api_paths"] == []
    for path in SLICE_PATHS[1:]:
        family = "/".join(path.split("/")[:3])
        assert any(candidate.startswith(family + "/") for candidate in ui_manifest["api_paths"]), path


def test_feature_truth_sources_contain_no_private_paths_or_people() -> None:
    javascript = read_workbench_asset("workbench.js")
    combined = "\n".join((*ACCEPTED_FEATURE_IDS, javascript))
    for forbidden in ("C:\\Users\\", "D:\\dev\\", "@example.com"):
        assert forbidden not in combined


def test_public_catalog_promotes_all_accepted_slices_without_preview_claims() -> None:
    catalog = Path("docs/features.md").read_text(encoding="utf-8")
    truth = Path("docs/GA_TODAY_FEATURE_TRUTH.md").read_text(encoding="utf-8")
    specialized = catalog.split("<h2>Verified specialized workbenches</h2>", 1)[1].split(
        "<h2>Verified Matter Productivity Studio</h2>", 1
    )[0]
    productivity = catalog.split("<h2>Verified Matter Productivity Studio</h2>", 1)[1].split(
        "<h2>Verified Add-on Studio</h2>", 1
    )[0]
    addons = catalog.split("<h2>Verified Add-on Studio</h2>", 1)[1].split(
        "<h2>Additional source capabilities under qualification</h2>", 1
    )[0]
    assert specialized.count("Verified end to end") == 24
    assert productivity.count("Verified end to end") == 10
    assert addons.count("Verified end to end") == 20
    assert "Usable with local-engine prerequisite" not in addons
    assert "bundled, hash-pinned whisper.cpp" in addons
    assert "Development preview" not in specialized
    assert truth.count("`verified_end_to_end`") >= 24
