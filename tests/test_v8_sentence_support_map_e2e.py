from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-v8-sentence-support-map-e2e.py"


def _module():
    specification = importlib.util.spec_from_file_location("v8_sentence_support_map_e2e", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_safe_map_state_reports_review_state_without_sentence_text() -> None:
    module = _module()
    state = module.safe_map_state(
        {
            "map_id": "sentence_map_fictional",
            "document_id": "document_fictional",
            "revision_id": "revision_fictional",
            "summary": {"sentence_count": 2, "supported_sentences": 1, "missing_context_sentences": 1},
            "sentences": [{"text": "private fictional text"}],
            "review_required": True,
            "filing_ready": False,
            "current_revision_match": True,
            "stale_for_current_draft": False,
        }
    )
    assert state["sentence_count"] == 2
    assert state["review_required"] is True
    assert state["filing_ready"] is False
    assert "private fictional text" not in str(state)
