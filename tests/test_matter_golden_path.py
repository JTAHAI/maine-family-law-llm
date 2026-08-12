from pathlib import Path

import pytest

from legal.matter.golden_path import MatterJourneyStore
from legal.matter.intake_workbench import IntakeWorkbenchError, MatterIntakeStore


def seeded(tmp_path: Path) -> tuple[MatterIntakeStore, MatterJourneyStore]:
    case = tmp_path / "case"
    case.mkdir()
    key = "synthetic-test-passphrase"
    intake = MatterIntakeStore(case, encryption_key=key)
    intake.create({"matter_id": "matter_demo", "matter_type_candidates": ["research_only"]})
    journey = MatterJourneyStore(case, encryption_key=key)
    return intake, journey


def test_journey_derives_machine_stages_and_guides_next_action(tmp_path: Path):
    intake, journey = seeded(tmp_path)
    first = journey.status("matter_demo", corpus_metrics={})
    assert first["completed_stage_count"] == 1
    assert first["next_action"]["stage"] == "procedural_posture"

    intake.posture("matter_demo", {"state": "unknown", "source_refs": []})
    intake.issue_tree(
        "matter_demo",
        {
            "issues": [
                {
                    "issue_id": "issue_schedule",
                    "issue_label": "Schedule question",
                    "supporting_records": [],
                    "contradicting_records": [],
                    "applicable_authority_candidates": [],
                    "missing_facts": [],
                    "missing_records": [],
                    "forms": [],
                    "deadlines_requiring_review": [],
                }
            ]
        },
    )
    progressed = journey.status("matter_demo", corpus_metrics={"document_count": 2})
    assert progressed["completed_stage_count"] == 4
    assert progressed["next_action"]["stage"] == "grounded_research"


def test_journey_requires_hash_bound_human_checkpoints(tmp_path: Path):
    _intake, journey = seeded(tmp_path)
    with pytest.raises(IntakeWorkbenchError):
        journey.record_checkpoint("matter_demo", {"stage": "grounded_research", "approved": True})
    research = journey.record_checkpoint(
        "matter_demo",
        {
            "stage": "grounded_research",
            "approved": True,
            "source_receipt_sha256": "a" * 64,
        },
    )
    review = journey.record_checkpoint(
        "matter_demo",
        {
            "stage": "human_review",
            "approved": True,
            "review_receipt_sha256": "b" * 64,
            "reviewer_role": "attorney",
        },
    )
    assert research["previous_event_hash"] == ""
    assert review["previous_event_hash"] == research["event_hash"]


def test_journey_reaches_review_complete_only_with_every_stage(tmp_path: Path):
    intake, journey = seeded(tmp_path)
    intake.posture("matter_demo", {"state": "unknown", "source_refs": []})
    intake.issue_tree(
        "matter_demo",
        {
            "issues": [
                {
                    "issue_id": "issue_scope",
                    "issue_label": "Scope question",
                    "supporting_records": [],
                    "contradicting_records": [],
                    "applicable_authority_candidates": [],
                    "missing_facts": [],
                    "missing_records": [],
                    "forms": [],
                    "deadlines_requiring_review": [],
                }
            ]
        },
    )
    journey.record_checkpoint(
        "matter_demo",
        {
            "stage": "grounded_research",
            "approved": True,
            "source_receipt_sha256": "c" * 64,
        },
    )
    journey.record_checkpoint(
        "matter_demo",
        {
            "stage": "human_review",
            "approved": True,
            "review_receipt_sha256": "d" * 64,
        },
    )
    status = journey.status("matter_demo", corpus_metrics={"document_count": 1})
    assert status["status"] == "review_complete"
    assert status["progress"] == 1.0
    assert status["review_required"] is False
