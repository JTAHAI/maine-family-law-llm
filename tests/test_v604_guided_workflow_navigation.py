from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "maine_family_law_llm" / "ui"
MIRROR_ROOT = ROOT / "src" / "maine_family_law_llm" / "ui"


def test_guided_workflow_navigation_reuses_the_guarded_workspaces() -> None:
    html = (UI_ROOT / "workbench.html").read_text(encoding="utf-8")
    js = (UI_ROOT / "workbench.js").read_text(encoding="utf-8")

    assert 'id="workflow-navigator"' in html
    for workflow in ("research", "matter", "authority", "intelligence", "draft", "privacy"):
        assert f'data-workflow-action="{workflow}"' in html
    for workflow in ("timeline", "claims", "coverage", "enforcement", "findings", "forms", "command"):
        assert f'data-workflow-action="{workflow}"' not in html

    for marker in (
        "function setWorkflowFocus(workflow)",
        "question?.focus({preventScroll: true})",
        "setDrawerOpen(true, 'setup')",
        "openDocumentIntelligence(button)",
        "await openDocumentWorkspace()",
        "openOverlay(privacyOverlay)",
    ):
        assert marker in js


def test_guided_workflow_navigation_is_responsive_and_mirrored() -> None:
    css = (UI_ROOT / "workbench.css").read_text(encoding="utf-8")
    assert ".workflow-navigator" in css
    assert ".workflow-action.is-active" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(118px, 1fr))" in css
    assert ".matter-command-center-layout" in css

    for name in ("workbench.html", "workbench.js", "workbench.css"):
        assert (UI_ROOT / name).read_bytes() == (MIRROR_ROOT / name).read_bytes()


def test_document_workflow_stages_navigate_existing_review_controls() -> None:
    html = (UI_ROOT / "workbench.html").read_text(encoding="utf-8")
    js = (UI_ROOT / "workbench.js").read_text(encoding="utf-8")

    assert 'id="document-workspace-stages"' in html
    for stage in ("compose", "revision", "filing"):
        assert f'data-document-stage="{stage}"' in html
        assert f'data-document-stage-target="{stage}"' in html
    for stage in ("findings", "word"):
        assert f'data-document-stage="{stage}"' not in html
        assert f'data-document-stage-target="{stage}" hidden' in html

    assert "function openDocumentWorkspaceStage(stageName)" in js
    assert "target.scrollIntoView" in js
    assert "documentWorkspaceStages.forEach" in js


def test_advanced_workflows_explain_their_review_sequence() -> None:
    html = (UI_ROOT / "workbench.html").read_text(encoding="utf-8")
    css = (UI_ROOT / "workbench.css").read_text(encoding="utf-8")

    assert html.count('class="local-operation-flow"') == 3
    assert 'class="local-operation-flow local-operation-flow-warning"' in html
    assert "Create immutable packet" in html
    assert "Do not self-certify" in html
    assert ".local-operation-flow-warning" in css
    assert 'id="matter-command-center-overlay"' in html
    assert 'id="matter-command-center-status"' in html
