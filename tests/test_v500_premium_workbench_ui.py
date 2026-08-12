"""v5.0.0 premium family-justice workbench regression coverage."""

from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html
from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_PASS_MARKER, UI_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_v500_release_identity_and_store_version_are_aligned() -> None:
    assert VERSION == "7.0.0"
    assert PACKAGE_VERSION == "7.0.0.0"
    assert BUILD_NUMBER == 52
    assert UI_PASS_MARKER == "v7.0.0-ga"
    assert UI_VERSION.endswith("-b52")
    identity_path = ROOT / "store/msix/identity.local.json"
    if not identity_path.is_file():
        identity_path = ROOT / "store/msix/identity.example.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    assert identity["package_version"] == PACKAGE_VERSION


def test_v500_html_matches_approved_three_column_workbench_contract() -> None:
    html = render_local_workbench_html()
    for marker in (
        'class="app-shell v5-workbench"',
        'class="v5-control-bar"',
        'class="workbench-rail"',
        'class="right-rail evidence-drawer"',
        'data-ui-generation="v5-premium-workbench"',
        'data-drawer="open"',
        'aria-hidden="false" aria-label="Research controls and evidence"',
        "FOR OUR CHILDREN &amp; FAMILIES",
        "Source-backed research workbench for FOCAF",
        "Prompt shortcuts",
        "Question starters",
        "Starter packs",
        "Quick actions",
        "Evidence inventory",
        "Local only",
    ):
        assert marker in html

    for element_id in (
        "audience",
        "answer-style",
        "topic-filter",
        "matter-context",
        "command-palette-button",
        "privacy-button",
        "matter-button",
        "focus-mode-button",
        "question",
        "search-mode",
        "child-impact-lens",
        "source-cards",
        "corpus-select",
        "inventory-status",
    ):
        assert f'id="{element_id}"' in html


def test_v500_css_has_desktop_density_and_responsive_drawer() -> None:
    css = read_workbench_asset("workbench.css")
    assert "v5.0.0 premium family-justice workbench" in css
    assert "grid-template-columns: minmax(520px, 1fr) 280px 350px" in css
    assert ".workbench-rail" in css
    assert ".v5-source-cards" in css
    assert ".chat-source-lanes" in css
    assert "@media (max-width: 1359px)" in css
    assert "@media (max-width: 959px)" in css
    assert "@media (max-width: 719px)" in css
    assert 'body[data-drawer="closed"] .evidence-drawer' in css


def test_v500_javascript_renders_rich_chat_sources_and_clickable_records() -> None:
    js = read_workbench_asset("workbench.js")
    assert "function renderInlineEvidence(payload)" in js
    assert "function renderRecordGroups(groups)" in js
    assert "function addMessage(role, text, payload = null)" in js
    assert "renderRecordGroups(payload.record_groups)" in js
    assert "bindRecordOpenActions(wrapper)" in js
    assert "data-inline-open-workspace" in js
    assert "data-message-evidence-jump" in js
    assert "syncResponsiveLayout({initial: true})" in js
    assert "window.matchMedia('(min-width: 960px)')" in js
    assert "window.matchMedia('(min-width: 1360px)')" in js
    assert "syncResponsiveLayout({initial: true})" in js
    assert "/api/records/open/" in js
    assert "file://" not in js.lower()


def test_v500_visual_rebuild_evidence_is_packaged_as_documentation() -> None:
    report = ROOT / "docs" / "ui-rebuild" / "v5.0.0-rebuild-report.md"
    evidence = ROOT / "docs" / "ui-rebuild" / "v5.0.0-responsive-ux-evidence.json"
    assert report.is_file()
    assert evidence.is_file()
    assert "closely matches the approved design" in report.read_text(encoding="utf-8").lower()
