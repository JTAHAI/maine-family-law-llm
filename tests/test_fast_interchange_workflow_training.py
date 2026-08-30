from __future__ import annotations

import socket

import pytest

from scripts.fast_interchange_acceptance_cases import acceptance_cases
from scripts.fast_interchange_workflow_training_data import (
    DATASET_CLASS,
    DATASET_SCOPE,
    TRAINING_VARIANT_COUNT,
    dataset_digest,
    workflow_training_rows,
)
from scripts.train_fast_interchange_workflow_r0004 import _assert_candidate_root, _NetworkDenied
from scripts.verify_fast_interchange_workflow_r0004 import EXPECTED_SCOPE, _assert_inside_dist


def test_workflow_rows_are_partitioned_fictional_and_review_required() -> None:
    rows = workflow_training_rows()

    assert DATASET_CLASS == "synthetic_eval_data"
    assert "not_substantive_maine_law" in DATASET_SCOPE
    assert len(rows) == TRAINING_VARIANT_COUNT * 7
    assert len({row.row_id for row in rows}) == len(rows)
    assert len(dataset_digest(rows)) == 64
    assert {row.capability for row in rows} == {
        "intake_triage",
        "evidence_review",
        "authority_review",
        "drafting",
        "parenting_plan_review",
        "financial_disclosure_review",
        "safety_privacy_review",
    }
    assert all("Review required." in row.response for row in rows)
    assert all("Maine statute" not in row.prompt for row in rows)
    assert all("DEMO-" not in row.prompt + row.response for row in rows)


def test_workflow_training_rows_do_not_include_held_out_acceptance_prompts() -> None:
    training = {row.prompt for row in workflow_training_rows()}
    held_out = {case.prompt() for case in acceptance_cases()}

    assert training.isdisjoint(held_out)


def test_safety_rows_never_copy_the_fictional_contact_identifier() -> None:
    safety_rows = [
        row for row in workflow_training_rows() if row.capability == "safety_privacy_review"
    ]

    assert safety_rows
    assert all("SYNTHETIC-CONTACT-" not in row.response for row in safety_rows)
    assert all("[REDACTED]" in row.response for row in safety_rows)


def test_candidate_output_rejects_external_and_existing_paths(tmp_path) -> None:
    with pytest.raises(ValueError, match="candidate_output_must_be_new_child"):
        _assert_candidate_root(tmp_path / "outside-repository")


def test_candidate_acceptance_scope_and_evidence_path_fail_closed(tmp_path) -> None:
    assert "not_substantive_maine_law" in EXPECTED_SCOPE
    existing = tmp_path / "existing.json"
    existing.write_text("already exists", encoding="utf-8")
    with pytest.raises(ValueError, match="workflow_candidate_evidence_must_be_new"):
        _assert_inside_dist(existing, new=True)


def test_training_network_denial_is_scoped_and_restored() -> None:
    original = socket.socket.connect
    with _NetworkDenied():
        with pytest.raises(Exception, match="training_network_forbidden"):
            socket.socket.connect(object(), object())
    assert socket.socket.connect is original
