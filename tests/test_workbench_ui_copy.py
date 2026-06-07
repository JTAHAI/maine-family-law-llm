from __future__ import annotations

import json
from pathlib import Path

from app.services.status_labels import blocked_state_explanations, stable_status_labels


ROOT = Path(__file__).resolve().parents[1]


def test_workbench_ui_copy_covers_required_concepts_and_status_labels() -> None:
    payload = json.loads((ROOT / "configs" / "maine_workbench_ui_copy.json").read_text(encoding="utf-8"))
    for key in (
        "start_here",
        "choose_workflow",
        "missing_information",
        "review_queue",
        "outreach_not_started",
        "attorney_review_evidence_missing",
    ):
        assert key in payload["concepts"]
    labels = stable_status_labels()
    for key in (
        "needs_human_review",
        "blocked_from_filing_ready",
        "attorney_review_missing",
        "outreach_not_started",
        "does_not_count_for_ga",
    ):
        assert labels[key]


def test_blocked_state_explanations_do_not_imply_external_review_exists() -> None:
    explanations = blocked_state_explanations()
    assert "No real licensed Maine attorney review evidence" in explanations["attorney_review_missing"]
    assert "emails have not been sent" in explanations["outreach_not_started"]
