import builtins

from maine_family_law_llm.feature_tiers import feature_tier_status


def test_runtime_reports_core_and_optional_feature_packs():
    status = feature_tier_status()
    assert status["packs"]["core"]["status"] == "available"
    assert status["core_workflows_available"] is True
    assert status["default_store_tier"] == "essential"


def test_pyinstaller_spec_has_a_low_footprint_default_and_full_opt_in():
    text = builtins.open("store/pyinstaller/maine_family_law_llm.spec", encoding="utf-8").read()
    assert 'MFL_STORE_FEATURE_TIER", "essential"' in text
    assert 'FEATURE_TIER == "full"' in text
    assert '"torch"' in text


def test_store_builder_skips_large_model_pack_for_essential_tier():
    text = builtins.open("scripts/build-store-runtime.ps1", encoding="utf-8").read()
    assert '[string]$FeatureTier = "essential"' in text
    assert 'if ($FeatureTier -eq "full")' in text
