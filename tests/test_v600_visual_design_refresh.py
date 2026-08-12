from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_PASS_MARKER, UI_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[1]
HTML_PATHS = [
    ROOT / "maine_family_law_llm" / "ui" / "workbench.html",
    ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html",
]
CSS_PATHS = [
    ROOT / "maine_family_law_llm" / "ui" / "workbench.css",
    ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.css",
]


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    bright, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def test_v600_release_identity() -> None:
    assert VERSION == "7.0.0"
    assert PACKAGE_VERSION == "7.0.0.0"
    assert BUILD_NUMBER == 52
    assert UI_PASS_MARKER == "v7.0.0-ga"
    assert UI_VERSION == "7.0.0-ga-b52"


def test_v600_ui_mirrors_match() -> None:
    assert HTML_PATHS[0].read_bytes() == HTML_PATHS[1].read_bytes()
    assert CSS_PATHS[0].read_bytes() == CSS_PATHS[1].read_bytes()


def test_v600_visual_generation_is_scoped_without_breaking_v5_contract() -> None:
    html = HTML_PATHS[0].read_text(encoding="utf-8")
    assert '<body class="v6-workbench"' in html
    assert 'class="app-shell v5-workbench"' in html
    assert 'data-ui-generation="v5-premium-workbench"' in html
    assert 'data-visual-generation="v6-visual-design-refresh"' in html
    assert 'class="v6-release-chip"' in html


def test_v600_policy_and_tokens_are_machine_readable() -> None:
    policy = json.loads((ROOT / "configs" / "maine_v6_visual_design_policy.json").read_text(encoding="utf-8"))
    tokens = json.loads((ROOT / "assets" / "brand" / "focaf_family_law_llm_brand_kit" / "data" / "v6-design-tokens.json").read_text(encoding="utf-8"))
    assert policy["product_version"] == VERSION
    assert policy["ui_build"] == BUILD_NUMBER
    assert policy["scope"] == "visual_refresh_without_workflow_rearchitecture"
    assert tokens["version"] == VERSION
    assert tokens["tokens"] == policy["palette"]


def test_v600_primary_palette_meets_text_contrast_targets() -> None:
    palette = json.loads((ROOT / "configs" / "maine_v6_visual_design_policy.json").read_text(encoding="utf-8"))["palette"]
    assert _contrast(palette["ink_950"], palette["paper_50"]) >= 12.0
    assert _contrast("#ffffff", palette["pine_700"]) >= 6.0
    assert _contrast("#ffffff", palette["atlantic_700"]) >= 7.0
    assert _contrast(palette["atlantic_900"], palette["paper_100"]) >= 10.0


def test_v600_accessibility_modes_are_present() -> None:
    css = CSS_PATHS[0].read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (prefers-contrast: more)" in css
    assert "@media (forced-colors: active)" in css
    assert "outline: 3px solid" in css
    assert "color-scheme: light" in css


def test_v600_uses_local_system_fonts_only() -> None:
    css = CSS_PATHS[0].read_text(encoding="utf-8")
    html = HTML_PATHS[0].read_text(encoding="utf-8")
    assert "@import" not in css
    assert "fonts.googleapis.com" not in css
    assert "fonts.googleapis.com" not in html
    assert "Segoe UI Variable Text" in css
    assert "Cascadia Mono" in css


def test_v600_refresh_covers_core_surfaces_and_modals() -> None:
    css = CSS_PATHS[0].read_text(encoding="utf-8")
    for marker in (
        ".v6-workbench .v5-workbench .constitutional-bar",
        ".v6-workbench .v5-control-bar",
        ".v6-workbench .v5-main-stage.main-stage",
        ".v6-workbench .v5-workbench .composer",
        ".v6-workbench .footerbar",
        ".record-inspector-modal",
        ".document-intelligence-modal",
        ".evidence-work-product-modal",
        ".retrieval-workbench-modal",
        ".release-pilot-hardening-modal",
    ):
        assert marker in css


def test_v600_release_documentation_exists() -> None:
    notes = (ROOT / "docs" / "release-notes-v6.0.0.md").read_text(encoding="utf-8")
    design = (ROOT / "docs" / "V6_0_VISUAL_DESIGN_REFRESH.md").read_text(encoding="utf-8")
    assert "Visual Design Refresh" in notes
    assert "No navigation or workflow rewrite" in design
    assert "6.0.0.0" in notes
