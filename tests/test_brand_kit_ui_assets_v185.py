from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRAND_ROOT = ROOT / "assets" / "brand" / "focaf_family_law_llm_brand_kit"


def test_v185_brand_kit_assets_are_first_class_repo_files() -> None:
    required = [
        BRAND_ROOT / "README.md",
        BRAND_ROOT / "BRAND_GUIDE.md",
        BRAND_ROOT / "asset-manifest.json",
        BRAND_ROOT / "css" / "tokens.css",
        BRAND_ROOT / "css" / "focaf-family-law-llm-theme.css",
        BRAND_ROOT / "data" / "design-tokens.json",
        BRAND_ROOT / "assets" / "logo" / "focaf-family-law-llm-mark.svg",
        BRAND_ROOT / "assets" / "logo" / "focaf-family-law-llm-horizontal.svg",
        BRAND_ROOT / "assets" / "social" / "focaf-family-law-llm-social-card.svg",
        BRAND_ROOT / "assets" / "favicon" / "favicon.svg",
        BRAND_ROOT / "assets" / "favicon" / "site.webmanifest",
    ]
    for path in required:
        assert path.is_file(), f"missing brand asset: {path}"


def test_v185_local_workbench_uses_brand_assets_and_visible_beautiful_shell() -> None:
    from maine_family_law_llm.local_workbench_ui import render_local_workbench_html
    from maine_family_law_llm.version import UI_FOOTER_LABEL, UI_VERSION

    html = render_local_workbench_html()
    assert f'data-ui-version="{UI_VERSION}"' in html
    assert 'data-brand-kit="focaf_family_law_llm_brand_kit"' in html
    assert 'id="focaf-brand-hero"' in html
    assert '/brand-assets/assets/logo/focaf-family-law-llm-mark.svg' in html
    assert '/brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg' in html
    assert '/brand-assets/assets/social/focaf-family-law-llm-social-card.svg' in html
    assert '/brand-assets/css/focaf-family-law-llm-theme.css' in html
    assert 'WE THE PEOPLE' in html
    assert '... establish JUSTICE ...' in html
    assert 'Justice does not belong to one institution or one profession' in html
    assert UI_FOOTER_LABEL in html
    assert 'Brand assets loaded from /brand-assets' in html
    assert f"window.__MFL_WORKBENCH_UI_VERSION = '{UI_VERSION}'" in html
    assert "question.addEventListener('keydown'" in html
    assert "event.key === 'Enter' && !event.shiftKey" in html


def test_v185_runtime_diagnostics_reports_brand_asset_mount() -> None:
    pytest.importorskip("fastapi")
    from maine_family_law_llm import __version__, api
    from maine_family_law_llm.version import UI_VERSION

    payload = api.runtime_diagnostics()
    assert payload["version"] == __version__
    assert payload["ui_version"] == UI_VERSION
    assert payload["brand_assets_mounted"] is True
    assert payload["brand_kit"] == "assets/brand/focaf_family_law_llm_brand_kit"
    assert payload["constitutional_chat_shell_v208"] is True


def test_v185_brand_assets_are_served_by_local_api() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm.api import app

    assert app is not None
    client = TestClient(app)
    logo = client.get("/brand-assets/assets/logo/focaf-family-law-llm-mark.svg")
    assert logo.status_code == 200
    assert "svg" in logo.text.lower()
    css = client.get("/brand-assets/css/focaf-family-law-llm-theme.css")
    assert css.status_code == 200
    assert "--focaf-river-teal" in css.text
