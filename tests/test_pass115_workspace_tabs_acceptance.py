from pathlib import Path

import pytest

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.product.workspace_tabs import WorkspaceTabsStore


def test_pass115_encrypts_active_matter_tabs_and_retains_a_review_boundary(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = WorkspaceTabsStore(root, encryption_key="fictional-test-key")
    created = store.create(
        {
            "tab_id": "record_review_001",
            "kind": "record",
            "label": "Fictional order review",
            "target": {"record_id": "record_001", "source_hash": "a" * 64, "page": 1},
            "user_confirmed": True,
        }
    )
    assert created["tab"]["review_required"] is True
    assert "Fictional order review" not in store.path.read_text(encoding="utf-8")
    assert store.target("record_review_001")["target"]["record_id"] == "record_001"
    created_draft = store.create(
        {
            "tab_id": "draft_review_001",
            "kind": "draft",
            "label": "Fictional saved draft",
            "target": {"document_id": "draft_001"},
            "user_confirmed": True,
        }
    )
    assert store.activate("record_review_001")["active_tab_id"] == "record_review_001"
    assert store.close(created_draft["tab"]["tab_id"])["status"] == "closed_review_required"


def test_pass115_refuses_unconfirmed_or_path_like_targets(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = WorkspaceTabsStore(root, encryption_key="fictional-test-key")
    with pytest.raises(IntakeWorkbenchError):
        store.create({"tab_id": "record_001", "kind": "record", "label": "Record", "target": {}, "user_confirmed": False})
    with pytest.raises(IntakeWorkbenchError):
        store.create(
            {
                "tab_id": "record_001",
                "kind": "record",
                "label": "Record",
                "target": {"record_id": "C:\\private.docx", "source_hash": "a" * 64},
                "user_confirmed": True,
            }
        )


def test_pass115_shipped_api_and_ui_expose_revalidated_tabs_without_chat_reset():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    api = Path("src/maine_family_law_llm/api.py").read_text(encoding="utf-8")
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert '"/api/workspace-tabs"' in api
    assert "workspace_tab_record_not_in_active_matter" in api
    assert "Workspace tabs" in ui
    assert "chat state remains unchanged" in ui
