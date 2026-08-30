from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.local_workbench_ui import render_local_workbench_html
from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_FOOTER_LABEL, UI_VERSION, VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_versions_and_about_surface_are_consistent() -> None:
    assert VERSION == "8.0.1"
    assert PACKAGE_VERSION == "8.0.1.0"
    assert BUILD_NUMBER == 54
    assert UI_VERSION == "8.0.1-ga-b54"
    assert UI_FOOTER_LABEL == "v8.0.1"
    assert 'version = "8.0.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    html = render_local_workbench_html()
    assert "8.0.1" in html
    assert "8.0.1.0" in html
    assert "6.0.4-extended-hardening-full-source.zip" not in html


def test_store_identity_and_manifest_contract_are_unchanged_except_version() -> None:
    identity = json.loads((ROOT / "store/msix/identity.local.json").read_text(encoding="utf-8"))
    assert identity == {
        "identity_name": "TAHAIWebServices.MaineFamilyLawLLM",
        "publisher": "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868",
        "publisher_display_name": "TAHAI Web Services",
        "package_display_name": "Maine Family Law LLM",
        "package_version": "8.0.1.0",
    }
    manifest = (ROOT / "store/msix/AppxManifest.xml.in").read_text(encoding="utf-8")
    assert 'ProcessorArchitecture="x64"' in manifest
    assert '<Resource Language="en-us" />' in manifest
    assert "x-generate" not in manifest.casefold()
    assert "MaineFamilyLawLLM.exe" in manifest


def test_v700_public_scope_is_small_verified_and_hidden_slices_stay_hidden() -> None:
    scope = json.loads((ROOT / "configs/v700_release_scope.json").read_text(encoding="utf-8"))
    public = {row["feature_id"] for row in scope["public_features"]}
    hidden = {row["feature_id"] for row in scope["hidden_features"]}
    assert len(public) == 16
    assert all(row["status"] == "verified_end_to_end" and row["advertised"] for row in scope["public_features"])
    assert {f"slice_{number}" for number in range(21, 45)} <= hidden
    assert not (public & hidden)
