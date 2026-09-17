"""Qualification machinery tests are not real-model quality evidence."""

import copy
import json
import math
from types import SimpleNamespace

import pytest

from scripts import acquire_compact_model_candidates as acquisition
from scripts.verify_compact_nli_candidate import (
    LABELS,
    fixture,
    input_pair,
    qualification_exit_code,
    score_rows,
    validate_worker_result,
)


def perfect_rows():
    return [
        {
            "id": row["id"],
            "probabilities": [float(label == row["expected"]) for label in LABELS],
            "seconds": 0.01,
        }
        for row in fixture()
    ]


def test_expected_labels_and_case_ids_are_not_model_input():
    for case in fixture():
        changed = {**case, "id": "different", "expected": "unknown"}
        assert input_pair(changed) == input_pair(case)
        assert len(input_pair(case)) == 2


def test_acquisition_budget_includes_selected_runtime_before_any_file_download(monkeypatch):
    selected = dict(acquisition.CATALOG["text-relation-nli"])
    selected["selected_runtime_bytes"] = acquisition.MAX_MODEL_BYTES - 7
    monkeypatch.setitem(acquisition.CATALOG, "text-relation-nli", selected)
    metadata = {
        "sha": selected["revision"],
        "cardData": {"license": "apache-2.0"},
        "siblings": [{"rfilename": name, "size": 2} for name in selected["files"]],
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, size):
            yield json.dumps(metadata).encode()

    monkeypatch.setattr(acquisition, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(acquisition, "download", lambda *args: pytest.fail("No download allowed"))
    with pytest.raises(ValueError, match="complete_package_exceeds_budget"):
        acquisition.acquire("text-relation-nli", session=SimpleNamespace())


def test_software_fixture_has_balanced_labels_and_unique_ids():
    rows = fixture()
    assert len({r["id"] for r in rows}) == 24
    assert all("fictional" in r["premise"].lower() for r in rows)
    assert {label: sum(r["expected"] == label for r in rows) for label in LABELS} == {
        "contradiction": 8,
        "entailment": 8,
        "neutral": 8,
    }


def test_even_perfect_software_challenge_cannot_mean_ga():
    report = score_rows(perfect_rows())
    assert report["correct"] == 24
    assert report["false_entailments"] == 0
    assert report["ga_ready"] is False
    assert report["probabilities_are_not_calibrated_truth_confidence"] is True


def test_separate_challenge_is_balanced_and_disjoint():
    rows = fixture("attribution36")
    assert len({case["id"] for case in rows}) == 36
    assert not {input_pair(case) for case in rows} & {input_pair(case) for case in fixture()}
    for split in ("cal", "eval"):
        selected = [case for case in rows if case["split"] == split]
        assert len(selected) == 18
        assert all(sum(case["expected"] == label for case in selected) == 6 for label in LABELS)
        assert len({case["category"] for case in selected}) == 6


def test_no_empty_or_unknown_qualification_set():
    with pytest.raises(ValueError, match="unknown_fictional_challenge"):
        fixture("arbitrary-input")
    with pytest.raises(ValueError, match="invalid_nli_fixture"):
        score_rows([], [])


@pytest.mark.parametrize("mutation", ["extra", "hash", "network", "memory", "timing", "version"])
def test_worker_measurements_cannot_overwrite_host_admission_or_fixture(mutation):
    result = {
        "rows": perfect_rows(),
        "load_seconds": 1.0,
        "peak_rss_bytes": 100,
        "torch_version": "2.13.0",
        "network_attempt_detected": False,
        "fixture_sha256": "a" * 64,
    }
    assert validate_worker_result(result, "a" * 64) == result
    if mutation == "extra":
        result["ga_ready"] = True
    elif mutation == "hash":
        result["fixture_sha256"] = "b" * 64
    elif mutation == "network":
        result["network_attempt_detected"] = True
    elif mutation == "memory":
        result["peak_rss_bytes"] = 4 * 1024**3
    elif mutation == "timing":
        result["load_seconds"] = math.nan
    else:
        result["torch_version"] = "private path / value"
    with pytest.raises(ValueError, match="worker_envelope_invalid"):
        validate_worker_result(result, "a" * 64)


def test_false_entailments_are_counted_without_relabeling():
    rows = perfect_rows()
    for row in rows:
        row["probabilities"] = [0, 1, 0]
    report = score_rows(rows)
    assert report["correct"] == 8
    assert report["false_entailments"] == 16
    assert report["synthetic_challenge_passed"] is False


def test_command_failure_cannot_be_hidden_by_successful_model_execution():
    assert qualification_exit_code({"errors": [], "metrics": {}}) == 1
    assert (
        qualification_exit_code({"errors": [], "metrics": {"synthetic_challenge_passed": False}})
        == 1
    )
    assert qualification_exit_code({"errors": [{"kind": "RuntimeError"}]}) == 2
    assert (
        qualification_exit_code({"errors": [], "metrics": {"synthetic_challenge_passed": True}})
        == 0
    )


@pytest.mark.parametrize(
    "values",
    [
        [],
        [0, 1],
        [0, 1, 0, 0],
        [0, math.nan, 0],
        [0, math.inf, 0],
        [-1, 1, 1],
        [0, True, 0],
        [0.1, 0.1, 0.1],
        "entailment",
    ],
)
def test_invalid_probabilities_fail_closed(values):
    rows = perfect_rows()
    rows[0]["probabilities"] = values
    with pytest.raises(ValueError, match="invalid_nli_output"):
        score_rows(rows)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "extra", "duration"])
def test_incomplete_or_forged_output_fails_closed(mutation):
    rows = copy.deepcopy(perfect_rows())
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[0]["id"] = rows[1]["id"]
    elif mutation == "unknown":
        rows[0]["id"] = "unknown"
    elif mutation == "extra":
        rows[0]["ga_ready"] = True
    else:
        rows[0]["seconds"] = math.nan
    with pytest.raises(ValueError):
        score_rows(rows)
