"""Current release identity advances without enabling failed specialist candidates."""

import json
from pathlib import Path

from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_current_scope_versions_and_specialist_exclusion():
    scope = json.loads((ROOT / "configs/v902_release_scope.json").read_text())
    previous = json.loads((ROOT / "configs/v901_release_scope.json").read_text())
    truth = json.loads((ROOT / "configs/release_feature_truth.json").read_text())
    identity = json.loads((ROOT / "store/msix/identity.example.json").read_text())
    assert VERSION == scope["release"] == truth["release"]["product_version"] == "9.0.2"
    assert PACKAGE_VERSION == scope["package_version"] == identity["package_version"] == "9.0.2.0"
    assert BUILD_NUMBER == 58
    assert tuple(map(int, PACKAGE_VERSION.split("."))) > tuple(map(int, previous["package_version"].split(".")))
    assert truth["release"]["release_scope"] == "configs/v902_release_scope.json"
    assert scope["new_bundled_legal_model_ids"] == []
    assert scope["new_public_feature_ids"] == []
    assert scope["previous_maintenance_scope_reference"] == "configs/v901_release_scope.json"
    assert previous["new_public_feature_ids"] == ["optional_local_qwen_source_review", "consent_bound_local_ai_setup"]
    assert scope["model_import_requires_production_admission"] is True
    assert scope["storage_schema_change"] is False
    assert scope["automatic_downloads"] is False
    assert identity["identity_name"] == "TAHAIWebServices.MaineFamilyLawLLM"
    assert identity["publisher"] == "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
    assert (ROOT / "src/maine_family_law_llm/version.py").read_bytes() == (
        ROOT / "maine_family_law_llm/version.py"
    ).read_bytes()
