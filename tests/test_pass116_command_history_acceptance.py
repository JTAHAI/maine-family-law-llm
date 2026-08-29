from pathlib import Path

import pytest

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.product.command_history import CommandHistoryStore


def test_pass116_encrypts_history_and_allows_only_read_replay_without_new_confirmation(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = CommandHistoryStore(root, encryption_key="fictional-test-key")
    saved = store.record(
        {
            "command_id": "search_001",
            "operation": "matter_search",
            "kind": "read",
            "parameters": {"query": "fictional order"},
        }
    )
    assert saved["command"]["review_required"] is True
    assert "fictional order" not in store.path.read_text(encoding="utf-8")
    replay = store.replay("search_001")
    assert replay["execute"] is True
    assert replay["status"] == "safe_read_replay_allowed"


def test_pass116_mutations_need_initial_and_fresh_confirmation(tmp_path: Path):
    root = tmp_path / "fictional_matter"
    root.mkdir()
    store = CommandHistoryStore(root, encryption_key="fictional-test-key")
    with pytest.raises(IntakeWorkbenchError):
        store.record(
            {
                "command_id": "clear_001",
                "operation": "clear_recent_work",
                "kind": "mutation",
                "parameters": {"target_id": "chat"},
            }
        )
    store.record(
        {
            "command_id": "clear_001",
            "operation": "clear_recent_work",
            "kind": "mutation",
            "parameters": {"target_id": "chat"},
            "user_confirmed": True,
        }
    )
    assert store.replay("clear_001")["status"] == "reconfirmation_required"
    confirmed = store.replay("clear_001", reconfirmed=True)
    assert confirmed["execute"] is False
    assert confirmed["status"] == "mutation_replay_reconfirmed_not_executed"


def test_pass116_shipped_api_and_ui_hold_the_replay_boundary():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    api = Path("src/maine_family_law_llm/api.py").read_text(encoding="utf-8")
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert '"/api/command-history"' in api
    assert "command_history_replay_not_allowed" in api
    assert "Command history" in ui
    assert "mutation was not executed" in ui
