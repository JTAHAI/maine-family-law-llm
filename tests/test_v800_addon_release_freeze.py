from __future__ import annotations

import json
from pathlib import Path

from legal.addons import ADDON_IDS
from maine_family_law_llm.local_workbench_ui import render_local_workbench_html
from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_FOOTER_LABEL, UI_VERSION, VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_v800_canonical_versions_and_about_surface_are_consistent() -> None:
    assert VERSION == "8.0.1"
    assert PACKAGE_VERSION == "8.0.1.0"
    assert BUILD_NUMBER == 54
    assert UI_VERSION == "8.0.1-ga-b54"
    assert UI_FOOTER_LABEL == "v8.0.1"
    assert 'version = "8.0.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    html = render_local_workbench_html()
    assert "8.0.1" in html
    assert "8.0.1.0" in html


def test_v800_store_identity_is_preserved_with_new_version() -> None:
    identity = json.loads((ROOT / "store/msix/identity.example.json").read_text(encoding="utf-8"))
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


def test_v800_release_scope_contains_all_and_only_verified_addons() -> None:
    scope = json.loads((ROOT / "configs/v800_release_scope.json").read_text(encoding="utf-8"))
    assert scope["decision"] == "VERSION_FROZEN"
    assert scope["acceptance_status"] == "verified_end_to_end"
    assert set(scope["public_addon_features"]) == set(ADDON_IDS)
    assert scope["release_boundaries"]["review_required"] is True
    assert scope["release_boundaries"]["enterprise_organizational_validation_claimed"] is False
