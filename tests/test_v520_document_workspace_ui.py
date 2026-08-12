"""v5.2 in-app document handling, drafting, and Word review UI contracts."""

from __future__ import annotations

from pathlib import Path

from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def test_document_workspace_is_a_large_main_window_modal() -> None:
    html = render_local_workbench_html()
    for marker in (
        'id="document-workspace"',
        'id="document-workspace-editor"',
        'id="document-workspace-diff"',
        'id="document-workspace-history"',
        'id="document-workspace-docx-load"',
        'id="document-workspace-docx-apply"',
        'Documents &amp; drafting',
        'Original Word files are never overwritten.',
        'Commit reviewed changes',
    ):
        assert marker in html


def test_chat_and_evidence_cards_expose_document_actions() -> None:
    js = read_workbench_asset("workbench.js")
    for marker in (
        'data-message-save-draft',
        'Save as draft',
        'data-inline-draft-record',
        'Draft from record',
        'function saveAnswerAsDraft(',
        'function importRecordToWorkspace(',
        "'/api/document-workspace/import-record'",
        "'/api/document-workspace/documents'",
        'Canonical filing gate',
    ):
        assert marker in js


def test_revision_and_deletion_mutations_require_explicit_user_confirmation() -> None:
    js = read_workbench_asset("workbench.js")
    assert "window.confirm('Commit this reviewed revision" in js
    assert 'confirmed: true' in js
    assert '/delete-request' in js
    assert 'Move “${active.title}” to the local trash?' in js
    assert 'Original preserved' in js or 'original preserved' in js


def test_word_edits_create_new_tracked_copy() -> None:
    js = read_workbench_asset("workbench.js")
    for marker in (
        '/docx/paragraphs?start=1&limit=300',
        '/docx/tracked-edit',
        'Create a NEW Word copy with this tracked change?',
        'Download tracked Word copy',
        'hash-anchored paragraph',
    ):
        assert marker in js


def test_document_workspace_css_is_large_responsive_and_main_window_focused() -> None:
    css = read_workbench_asset("workbench.css")
    for marker in (
        '.document-workspace-modal',
        'inset: 18px;',
        '.document-workspace-layout',
        '.document-workspace-editor-pane',
        '.document-workspace-review-pane',
        '.document-diff-line.is-add',
        '.message-draft-action',
        'body.document-workspace-open',
    ):
        assert marker in css


def test_ui_asset_mirrors_are_identical_after_document_workspace_upgrade() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("workbench.css", "workbench.html", "workbench.js"):
        assert (root / "src/maine_family_law_llm/ui" / name).read_bytes() == (
            root / "maine_family_law_llm/ui" / name
        ).read_bytes()
