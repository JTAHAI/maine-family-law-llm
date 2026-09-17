import json
import math
import sys
from types import SimpleNamespace

import pytest

from scripts import verify_ranker_abstention as experiment
from scripts.compact_ranker_abstention_challenge import CALIBRATION, EVALUATION


def row(identifier="cal-1", score=1.0, expected=None, top=0):
    return dict(id=identifier, score=score, expected=expected, top=top)


def test_predeclared_partitions_valid_and_disjoint():
    experiment.validate_fixture(CALIBRATION, EVALUATION)
    assert len(CALIBRATION) == len(EVALUATION) == 16


@pytest.mark.parametrize("rows", [[], [row("eval-1")], [row(expected=0)]])
def test_cannot_fit_on_evaluation_or_without_negatives(rows):
    with pytest.raises(ValueError):
        experiment.freeze_cutoff(rows)


@pytest.mark.parametrize(
    "score", [True, float("nan"), float("inf"), -float("inf"), "1", sys.float_info.max]
)
def test_invalid_or_unbounded_score_cannot_produce_cutoff(score):
    with pytest.raises(ValueError):
        experiment.freeze_cutoff([row(score=score)])


def test_wrong_positive_answer_counts_as_unsafe_and_ties_do_not_pass():
    rows = [
        row(score=2.0),
        row("cal-2", score=4.0, expected=1, top=0),
        row("cal-3", score=4.0, expected=0),
    ]
    cutoff = experiment.freeze_cutoff(rows)
    assert cutoff == math.nextafter(4.0, math.inf)
    result = experiment.metrics(rows, cutoff)
    assert result["accepted"] == 0 and result["correct_answer_coverage"] == 0


def test_evaluation_wrong_answers_and_abstentions_are_not_hidden():
    result = experiment.metrics(
        [
            row("eval-1", expected=0, score=3),
            row("eval-2", expected=1, top=0, score=3),
            row("eval-3", score=3),
            row("eval-4", score=0),
        ],
        2.0,
    )
    assert result["accepted"] == 3 and result["false_answer_acceptances"] == 2
    assert result["correct_answer_coverage"] == 0.5 and result["abstained"] == 1


@pytest.mark.parametrize("failure", [None, "evaluation", "cleanup", "cutoff_tamper"])
def test_cutoff_frozen_before_evaluation_and_failures_preserved(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(experiment, "OUTPUT", tmp_path)
    monkeypatch.setattr(experiment, "pinned_inventory", lambda *_: ())

    class Worker:
        def __init__(self, *_args, **_kwargs):
            self.files = [SimpleNamespace(path=tmp_path / "model.safetensors", sha256="f" * 64)]
            self.completed_requests = 0
            self.peak_resident_bytes = 1
            self._process = None

        def warm(self):
            return None

        def rank(self, **request):
            assert set(request) == {"query", "matter_id", "passages"}
            assert all(
                set(p) == {"source_id", "matter_id", "lane", "text"} for p in request["passages"]
            )
            if self.completed_requests == 16:
                assert (tmp_path / "ranker-abstention-unit-cutoff.json").exists()
                if failure == "evaluation":
                    raise ValueError("private exception must not be printed")
                if failure == "cutoff_tamper":
                    (tmp_path / "ranker-abstention-unit-cutoff.json").write_text("changed fixture")
            self.completed_requests += 1
            return [
                {"source_index": 0, "relevance_score": 1.0},
                {"source_index": 1, "relevance_score": 0.0},
            ]

        def close(self):
            if failure == "cleanup":
                raise ValueError("private cleanup path")

    monkeypatch.setattr(experiment, "IsolatedCompactRanker", Worker)
    assert experiment.execute("unit") is (failure is None)
    path = tmp_path / "ranker-abstention-unit.json"
    report = json.loads(path.read_text())
    assert (
        not report["ga_ready"]
        and not report["production_admitted"]
        and not report["policy_installed"]
    )
    assert "private exception" not in path.read_text() and "private cleanup" not in path.read_text()
    with pytest.raises(ValueError, match="preserve_prior_evidence"):
        experiment.execute("unit")
