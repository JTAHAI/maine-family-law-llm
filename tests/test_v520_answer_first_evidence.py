"""v5.2 answer-first evidence and large source-preview UX regression tests."""

from __future__ import annotations

from pathlib import Path

from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def test_answer_specific_evidence_is_rendered_in_main_chat() -> None:
    js = read_workbench_asset("workbench.js")
    for marker in (
        "function renderInlineEvidence(payload)",
        "function renderInlineSourceCard(item, index, payload",
        "function bindInlineEvidenceActions(container, payload)",
        "function renderMainChatAnswer(text, payload)",
        "data-inline-evidence-panel",
        "data-inline-preview-source",
        "data-inline-inspect-record",
        "data-inline-open-record",
        "data-inline-inspect-page",
        "data-message-evidence-jump",
        "Evidence used in this answer",
        "Open the proof here—no side-panel hunt required.",
    ):
        assert marker in js


def test_inline_evidence_reuses_secure_existing_source_actions() -> None:
    js = read_workbench_asset("workbench.js")
    assert "openRecordInspector(recordOpenBindingForPayload(item, payload)" in js
    assert "openRecordOriginal(recordOpenBindingForPayload(item, payload)" in js
    assert "showSourcePreview(item, card, {pin: true})" in js
    assert "/inspect-source/" in js
    assert "/api/records/open/" in js
    assert "file://" not in js.lower()


def test_inline_preview_refuses_to_label_a_snippet_as_an_exact_span() -> None:
    js = read_workbench_asset("workbench.js")
    assert "const hasExactSpan = Number.isInteger(sourceSpan.start_offset)" in js
    assert "Exact source span unavailable" in js
    assert "no admitted character range" in js
    assert "pinpoint citation or verified quote" in js


def test_external_source_links_reject_active_or_file_schemes() -> None:
    js = read_workbench_asset("workbench.js")
    assert "function safeExternalUrl(value)" in js
    assert "parsed.protocol === 'https:' || parsed.protocol === 'http:'" in js
    assert "safeExternalUrl(item?.url || meta.url || meta.official_url)" in js


def test_source_preview_becomes_large_centered_modal_when_pinned() -> None:
    css = read_workbench_asset("workbench.css")
    for marker in (
        ".v5-workbench .chat-evidence-panel",
        ".v5-workbench .chat-evidence-grid",
        ".v5-workbench .chat-evidence-card",
        ".v5-workbench .message-evidence-jump",
        ".source-preview-flyout.is-pinned",
        "width: min(760px, calc(100vw - 30px));",
        "body.source-preview-open",
    ):
        assert marker in css
    js = read_workbench_asset("workbench.js")
    assert "sourcePreviewFlyout.setAttribute('aria-modal', sourcePreviewPinned ? 'true' : 'false')" in js
    assert "document.body.classList.toggle('source-preview-open', sourcePreviewPinned)" in js
    assert "event.key === 'Tab' && sourcePreviewPinned" in js


def test_help_copy_describes_inline_evidence_as_primary_path() -> None:
    html = render_local_workbench_html()
    assert "Answer-specific source cards and evidence actions appear directly in the assistant response" in html
    assert "Source cards now appear inside the main answer" in html
    assert "Evidence &amp; tools</strong> remains an optional workspace" in html


def test_ui_asset_mirrors_are_identical_after_answer_first_upgrade() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("workbench.css", "workbench.html", "workbench.js"):
        assert (root / "src/maine_family_law_llm/ui" / name).read_bytes() == (
            root / "maine_family_law_llm/ui" / name
        ).read_bytes()
