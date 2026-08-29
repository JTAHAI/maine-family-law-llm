from pathlib import Path

import pytest

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.product.recent_work import RecentWorkStore


def test_pass114_encrypts_matter_scoped_restore_point_and_preserves_review_boundary(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = RecentWorkStore(root, encryption_key="fictional-test-key")
    source_hash = "a" * 64
    saved = store.save(
        {
            "workspace_id": "chat",
            "scroll_position": 240,
            "selected_sources": [
                {"lane": "private_matter_record", "record_id": "record_001", "source_hash": source_hash, "page": 2}
            ],
            "unsent_draft": "Fictional unsent question for local review.",
        }
    )
    assert saved["restore_point"]["has_unsent_draft"] is True
    assert saved["restore_point"]["review_required"] is True
    assert "Fictional unsent question" not in store.path.read_text(encoding="utf-8")
    restored = store.get("chat")["restore_point"]
    assert restored["unsent_draft"] == "Fictional unsent question for local review."
    assert store.source("chat", 0)["source"]["source_hash"] == source_hash
    assert store.clear("chat")["status"] == "cleared"
    assert store.get("chat")["restore_point"] is None


def test_pass114_refuses_paths_and_unbounded_restore_data(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = RecentWorkStore(root, encryption_key="fictional-test-key")
    with pytest.raises(IntakeWorkbenchError):
        store.save(
            {
                "workspace_id": "chat",
                "selected_sources": [
                    {"lane": "private_matter_record", "record_id": "..\\private.docx", "source_hash": "a" * 64}
                ],
                "unsent_draft": "",
            }
        )
    with pytest.raises(IntakeWorkbenchError):
        store.save({"workspace_id": "chat", "unsent_draft": "x" * 40_000})


def test_pass114_shipped_api_and_ui_keep_restore_local_and_revalidated():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    api = Path("src/maine_family_law_llm/api.py").read_text(encoding="utf-8")
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert '"/api/recent-work"' in api
    assert "recent_work_source_not_in_active_matter" in api
    assert "Recent work is available" in ui
    assert "trackRecentWorkRecord(payload)" in ui
