from pathlib import Path

import pytest

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.product.bulk_review_queue import BulkReviewQueueStore


def test_pass117_encrypts_source_bound_queue_and_retains_review_status(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = BulkReviewQueueStore(root, encryption_key="fictional-test-key")
    created = store.create(
        {
            "item_id": "review_001",
            "kind": "claim",
            "label": "Fictional claim review",
            "source_ref": {"record_id": "record_001", "source_hash": "a" * 64, "page": 1},
            "user_confirmed": True,
        }
    )
    assert created["item"]["state"] == "new"
    assert "Fictional claim review" not in store.path.read_text(encoding="utf-8")
    triaged = store.triage("review_001", {"state": "qualified", "reviewer_safe_id": "reviewer_001", "user_confirmed": True})
    assert triaged["item"]["state"] == "qualified"
    assert store.source("review_001")["source"]["record_id"] == "record_001"


def test_pass117_refuses_unconfirmed_items_and_path_like_sources(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = BulkReviewQueueStore(root, encryption_key="fictional-test-key")
    with pytest.raises(IntakeWorkbenchError):
        store.create({"item_id": "review_001", "kind": "record", "label": "Review", "source_ref": {}, "user_confirmed": False})
    with pytest.raises(IntakeWorkbenchError):
        store.create({"item_id": "review_001", "kind": "record", "label": "Review", "source_ref": {"record_id": "..\\private", "source_hash": "a" * 64}, "user_confirmed": True})


def test_pass117_shipped_api_and_keyboard_ui_are_present():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    api = Path("src/maine_family_law_llm/api.py").read_text(encoding="utf-8")
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert '"/api/bulk-review-queue"' in api
    assert "bulk_review_source_not_in_active_matter" in api
    assert "Bulk review queue" in ui
    assert "Keyboard triage" in ui
