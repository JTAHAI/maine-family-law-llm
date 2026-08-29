from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.production import app
from maine_family_law_llm.production_ui import production_ui_manifest


def test_pass125_static_accessibility_audit_reports_production_markup_contracts() -> None:
    manifest = production_ui_manifest()
    audit = manifest["accessibility_audit"]

    assert manifest["status"] == "pass", manifest
    assert audit["status"] == "pass", audit
    assert all(audit["checks"].values())
    assert audit["counts"]["main_landmarks"] == 1
    assert audit["counts"]["dialogs"] >= 1
    assert audit["counts"]["live_regions"] >= 1
    assert audit["audit_kind"] == "static_packaged_asset_audit"
    assert audit["limitations"]


def test_pass125_runtime_manifest_exposes_the_same_static_accessibility_audit() -> None:
    response = TestClient(app).get("/api/runtime/ui-manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["accessibility_audit"]["status"] == "pass"
    assert payload["accessibility_audit"]["checks"]["dialog_focus_return"] is True
