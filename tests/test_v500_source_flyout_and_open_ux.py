"""v5.0.0 source-card flyout, secure open, and nested-scrollbar UX hardening."""

from __future__ import annotations

from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html
from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION
from maine_family_law_llm.runtime_resilience import runtime_health_snapshot


def test_v500_build_26_keeps_store_version_stable() -> None:
    assert BUILD_NUMBER == 26
    assert PACKAGE_VERSION == "5.0.0.0"


def test_source_preview_shell_and_right_edge_offline_tooltip_exist() -> None:
    html = render_local_workbench_html()
    assert 'id="source-preview-flyout"' in html
    assert 'id="source-preview-body"' in html
    assert 'id="source-preview-actions"' in html
    assert 'id="source-preview-backdrop"' in html
    assert 'data-tooltip-edge="right"' in html
    assert 'id="local-status-dot"' in html
    assert 'Preview details' in html


def test_source_cards_open_private_records_and_use_scrollable_flyout() -> None:
    js = read_workbench_asset("workbench.js")
    for marker in (
        "function recordOpenBinding(item)",
        "function openRecordBinding(binding, page = 0)",
        "function showSourcePreview(item, owner",
        "sourcePreviewSuppressUntil",
        "localStatusDot?.classList.add('is-offline')",
        "data-open-source-record",
        "Open original",
        "Open at page",
        "/api/records/open/",
    ):
        assert marker in js
    assert "file://" not in js.lower()

    css = read_workbench_asset("workbench.css")
    assert ".source-preview-flyout" in css
    assert ".v5-workbench .constitutional-bar { overflow: visible; }" in css
    assert ".source-preview-body" in css
    assert "overflow: auto; overscroll-behavior: contain" in css
    assert ".v5-pack-list { display: grid; gap: 4px; max-height: none; overflow: visible; }" in css
    assert ".v5-answer-summary { margin: 8px 0; max-height: none; overflow: visible;" in css


def test_grouped_private_record_card_exposes_parent_id_for_token_binding(tmp_path: Path) -> None:
    groups = api._group_record_cards(tmp_path / "case", [{
        "source_id": "REC-1-P0002",
        "snippet": "matched passage",
        "metadata": {
            "parent_evidence_id": "REC-1",
            "page_number": 2,
            "source_locator": "Order.pdf#page=2",
            "source_type": "pdf_page",
        },
    }])
    assert groups[0]["source_id"] == "REC-1"
    assert len(groups[0]["source_token"]) == 64


def test_ui_asset_mirrors_remain_identical() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("workbench.css", "workbench.html", "workbench.js"):
        assert (root / "src/maine_family_law_llm/ui" / name).read_bytes() == (root / "maine_family_law_llm/ui" / name).read_bytes()


def test_clean_source_zip_health_does_not_require_optional_identity_local() -> None:
    runtime_health_snapshot.cache_clear()
    snapshot = runtime_health_snapshot()
    version_check = next(row for row in snapshot["checks"] if row["component"] == "version_alignment")
    assert version_check["status"] == "pass"
