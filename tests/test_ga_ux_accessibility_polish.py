from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR = ROOT / "maine_family_law_llm" / "ui"


def _read(name: str) -> str:
    return (SOURCE / name).read_text(encoding="utf-8")


def test_trust_status_keeps_matter_source_lanes_and_review_gate_visible() -> None:
    html = _read("workbench.html")
    js = _read("workbench.js")

    for marker in (
        'id="trust-status-strip"',
        'id="trust-authority-status"',
        'id="trust-record-status"',
        'id="trust-model-status"',
        'id="trust-review-status"',
        "function updateTrustStatus()",
        "Review required before reliance or export",
        "current-law wording remains blocked",
    ):
        assert marker in html + js


def test_workflow_controls_retain_native_button_semantics() -> None:
    html = _read("workbench.html")
    workflow = re.search(r'<div aria-label="Choose a guided workspace".*?</div>\s*</nav>', html, re.S)
    assert workflow
    assert 'role="group"' in workflow.group(0)
    assert 'role="listitem"' not in workflow.group(0)
    assert workflow.group(0).count("<button") == 6
    for hidden_action in ("timeline", "claims", "coverage", "enforcement", "findings", "forms", "command"):
        assert f'data-workflow-action="{hidden_action}"' not in workflow.group(0)


def test_private_record_lane_fails_closed_when_metadata_is_incomplete() -> None:
    js = _read("workbench.js")
    assert "function normalizedSourceLane(item)" in js
    assert "meta.record_open_token || item?.source_token" in js
    assert "meta.parent_evidence_id || meta.canonical_document_key || meta.safe_filename" in js
    assert "return 'unverified'" in js
    assert "data-source-lane=" in js
    assert "Unverified source" in js


def test_local_errors_are_safe_recoverable_and_do_not_render_raw_response_text() -> None:
    js = _read("workbench.js")
    for marker in (
        "function makeSafeLocalError",
        "function renderRecoverableError",
        "Affected scope",
        "What was preserved",
        "Safe recovery",
        "Technical details",
        "local_response_invalid",
    ):
        assert marker in js
    assert "const preview = text.replace" not in js
    assert "Your matter, draft, and original records were preserved." in js


def test_authority_failure_updates_visible_blocker_without_javascript_scope_error() -> None:
    js = _read("workbench.js")
    summary = js[js.index("function updateAuthorityLibrarySummary"):js.index("async function loadAuthorityStatus")]
    assert summary.index("const fresh") < summary.index("if (authorityLibraryClassCounts)")
    assert "Object.prototype.hasOwnProperty.call(payload, 'active')" in summary
    assert "authorityTrustPayload = {...payload, source_count: total}" in summary
    assert "updateTrustStatus()" in summary


def test_matter_switch_clears_prior_results_and_preserves_unsent_question() -> None:
    js = _read("workbench.js")
    switch = js[js.index("async function activateSelectedCorpus"):js.index("function sourceLane(item)")]
    for marker in (
        "const pendingQuestion = question?.value || ''",
        "activeRequestController?.abort()",
        "resetSession({preserveContext: true})",
        "question.value = pendingQuestion",
        "Prior-matter results were cleared",
    ):
        assert marker in switch


def test_tabs_dialogs_focus_motion_contrast_and_zoom_paths_are_hardened() -> None:
    js = _read("workbench.js")
    css = _read("workbench.css")
    for marker in (
        "panel.setAttribute('role', 'tabpanel')",
        "panel.setAttribute('aria-labelledby', tab.id)",
        "['ArrowLeft', 'ArrowRight', 'Home', 'End']",
        "const activeInside = activeOverlay.contains(document.activeElement)",
        "overlayReturnFocus",
    ):
        assert marker in js
    for marker in (
        "@media (prefers-reduced-motion: reduce)",
        "@media (forced-colors: active)",
        "@media (max-width: 520px)",
        "overflow-wrap: anywhere",
        "minmax(440px, 1fr)",
    ):
        assert marker in css


def test_production_ui_mirrors_remain_byte_identical() -> None:
    for name in ("workbench.html", "workbench.css", "workbench.js"):
        assert (SOURCE / name).read_bytes() == (MIRROR / name).read_bytes()


def test_unaccepted_workspaces_are_not_public_command_palette_entries() -> None:
    js = _read("workbench.js")
    for command_id in (
        "open_timeline",
        "open_claim_review",
        "open_record_coverage",
        "open_enforcement_ledger",
        "open_findings_review",
        "open_guided_forms",
        "open_command_center",
        "open_care_workspace",
        "open_safety_workspace",
        "open_schedule_workspace",
        "open_negotiation_workspace",
        "open_property_workspace",
        "open_modification_workspace",
        "open_foaa_workspace",
        "open_filing_workspace",
        "open_image_evidence_workspace",
        "open_email_integrity_workspace",
        "open_handoff_workspace",
        "open_language_workspace",
        "open_resource_workspace",
    ):
        assert f"id: '{command_id}'" not in js


def test_production_authority_update_hides_engineering_only_switches() -> None:
    js = _read("workbench.js")
    assert "[authorityFixtureMode, authorityDryRun, authorityForceRefresh]" in js
    assert "control.checked = false" in js
    assert "control.closest('label')?.setAttribute('hidden', '')" in js
