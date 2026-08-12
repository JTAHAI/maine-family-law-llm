from pathlib import Path

import pytest

from legal.evals.human_grounded import HumanEvalError, HumanEvalLedger


def add_case(ledger: HumanEvalLedger, case_id: str = "case-001"):
    return ledger.add_case(
        {
            "case_id": case_id,
            "task": "grounded_research",
            "artifact_sha256": "a" * 64,
            "data_class": "synthetic",
        }
    )


def review(ledger: HumanEvalLedger, reviewer_id: str, disposition: str = "approved"):
    return ledger.review(
        "case-001",
        {
            "reviewer_id": reviewer_id,
            "reviewer_role": "attorney",
            "disposition": disposition,
            "ratings": {
                "legal_accuracy": 5,
                "grounding": 5,
                "usefulness": 4,
                "boundary_safety": 5,
            },
            "finding_codes": [],
            "review_artifact_sha256": "b" * 64,
        },
    )


def test_two_independent_reviews_are_required_for_promotion(tmp_path: Path):
    ledger = HumanEvalLedger(tmp_path)
    add_case(ledger)
    assert review(ledger, "reviewer-1")["promotion_status"] == "awaiting_independent_reviews"
    assert review(ledger, "reviewer-2")["promotion_status"] == "promotion_eligible"
    ready = ledger.readiness(minimum_total=1, minimum_per_task=1)
    assert ready["status"] == "pass"
    assert ready["private_content_stored"] is False


def test_conflicting_reviews_require_hash_bound_adjudication(tmp_path: Path):
    ledger = HumanEvalLedger(tmp_path)
    add_case(ledger)
    review(ledger, "reviewer-1")
    conflict = review(ledger, "reviewer-2", "needs_correction")
    assert conflict["promotion_status"] == "adjudication_required"
    blocked = ledger.readiness(minimum_total=1, minimum_per_task=1)
    assert "human_eval_conflicts_unadjudicated" in blocked["blockers"]
    adjudicated = ledger.adjudicate(
        "case-001",
        {
            "approved": True,
            "reviewer_id": "reviewer-3",
            "disposition": "approved_with_notes",
            "receipt_sha256": "c" * 64,
        },
    )
    assert adjudicated["promotion_status"] == "promotion_eligible"


def test_duplicate_reviewer_and_unconsented_real_matter_are_refused(tmp_path: Path):
    ledger = HumanEvalLedger(tmp_path)
    add_case(ledger)
    review(ledger, "reviewer-1")
    with pytest.raises(HumanEvalError, match="human_eval_duplicate_reviewer"):
        review(ledger, "reviewer-1")
    with pytest.raises(HumanEvalError, match="human_eval_consent_receipt_sha256_invalid"):
        ledger.add_case(
            {
                "case_id": "case-real",
                "task": "grounded_research",
                "artifact_sha256": "d" * 64,
                "data_class": "consented_real_matter",
            }
        )


def test_default_release_threshold_refuses_seed_scale_evidence(tmp_path: Path):
    ledger = HumanEvalLedger(tmp_path)
    add_case(ledger)
    review(ledger, "reviewer-1")
    review(ledger, "reviewer-2")
    readiness = ledger.readiness()
    assert readiness["status"] == "blocked"
    assert "human_eval_minimum_total_not_met" in readiness["blockers"]
