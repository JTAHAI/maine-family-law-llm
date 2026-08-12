from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app
from maine_family_law_llm.production_ui import production_ui_manifest


def test_shipped_ui_is_the_single_validated_production_surface():
    manifest = production_ui_manifest()
    assert manifest["status"] == "pass", manifest
    assert manifest["asset_count"] == 3
    assert manifest["shadow_tsx_is_production"] is False
    assert manifest["offline_capable"] is True
    assert manifest["external_runtime_dependencies"] == []
    assert all(manifest["contracts"].values())
    assert all(len(item["sha256"]) == 64 for item in manifest["assets"].values())


def test_manifest_fails_closed_when_a_required_asset_is_missing(tmp_path: Path):
    for name in ("workbench.html", "workbench.css"):
        (tmp_path / name).write_text("placeholder", encoding="utf-8")
    manifest = production_ui_manifest(tmp_path)
    assert manifest["status"] == "fail"
    assert "missing_asset:workbench.js" in manifest["blockers"]


def test_production_api_publishes_ui_integrity_manifest():
    response = TestClient(app).get("/api/runtime/ui-manifest")
    assert response.status_code == 200
    assert response.json()["status"] == "pass"
