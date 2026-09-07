"""Maintenance identity advances without enabling failed specialist candidates."""

import json
from pathlib import Path

from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_v802_scope_versions_and_specialist_exclusion():
    scope = json.loads((ROOT / "configs/v802_release_scope.json").read_text())
    truth = json.loads((ROOT / "configs/release_feature_truth.json").read_text())
    identity = json.loads((ROOT / "store/msix/identity.example.json").read_text())
    assert VERSION == scope["release"] == truth["release"]["product_version"] == "8.0.2"
    assert PACKAGE_VERSION == scope["package_version"] == identity["package_version"] == "8.0.2.0"
    assert BUILD_NUMBER == 55
    assert tuple(map(int, PACKAGE_VERSION.split("."))) > (8, 0, 1, 0)
    assert truth["release"]["release_scope"] == "configs/v802_release_scope.json"
    assert scope["new_bundled_legal_model_ids"] == []
    assert scope["new_public_feature_ids"] == []
    assert scope["model_import_requires_production_admission"] is True
    assert scope["storage_schema_change"] is False
    assert scope["automatic_downloads"] is False
    assert identity["identity_name"] == "TAHAIWebServices.MaineFamilyLawLLM"
    assert identity["publisher"] == "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
    assert (ROOT / "src/maine_family_law_llm/version.py").read_bytes() == (
        ROOT / "maine_family_law_llm/version.py"
    ).read_bytes()
