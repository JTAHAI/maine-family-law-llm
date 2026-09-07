from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from scripts import run_mfl_correction_lane
from scripts.run_mfl_correction_lane import (
    completed_training,
    execute_stage,
    passed_regression,
    selected_specifications,
)


def test_training_completion_does_not_accept_partial_or_promoted_run(tmp_path):
    path = tmp_path / "result.json"
    data = {
        "status": "completed-local-research-only", "production_admitted": False,
        "train_examples": 12800, "examples_seen": 12800, "epochs": 1, "step": 6400,
        "identity": {"batch_size": 2},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert completed_training(path)
    for key, value in (("examples_seen", 8), ("production_admitted", True), ("step", 1)):
        path.write_text(json.dumps({**data, key: value}), encoding="utf-8")
        assert not completed_training(path)


def test_regression_requires_strict_pass_and_no_failures(tmp_path):
    path = tmp_path / "regression.json"
    data = {
        "decision": "LOCAL_RESEARCH_QUALITY_PASS", "failures": [],
        "quality": {"quality_gate_passed": True}, "production_admitted": False,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert passed_regression(path)
    path.write_text(json.dumps({**data, "failures": ["fabrication"]}), encoding="utf-8")
    assert not passed_regression(path)


def test_evidence_repair_can_run_without_starting_the_drafting_lane():
    selected = selected_specifications(("evidence_review",))
    assert [row[0] for row in selected] == ["evidence_review"]


@pytest.mark.parametrize(
    ("returncode", "creates_result", "valid", "expected"),
    (
        (0, True, True, True), (1, True, True, False),
        (0, False, True, False), (0, True, False, False),
    ),
)
def test_stage_persists_exit_log_and_completion_evidence(
    tmp_path, monkeypatch, returncode, creates_result, valid, expected
):
    script = tmp_path / "worker.py"
    script.write_text("# fictional worker\n", encoding="utf-8")
    completion = tmp_path / "complete.json"

    def fake_run(command, **kwargs):
        kwargs["stdout"].write("synthetic stage output\n")
        if creates_result:
            completion.write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode)

    monkeypatch.setattr(run_mfl_correction_lane, "run_child", fake_run)
    assert execute_stage(
        "train", [sys.executable, "-B", str(script)], output=tmp_path,
        environment=os.environ.copy(), completion=completion, validate=lambda _: valid,
        timeout=60,
    ) is expected
    record = json.loads((tmp_path / "train.json").read_text(encoding="utf-8"))
    assert record["status"] == ("passed" if expected else "failed")
    assert record["returncode"] == returncode
    assert len(record["script_sha256"]) == len(record["log_sha256"]) == 64
    assert record["duration_seconds"] >= 0


def test_stage_exception_is_recorded_not_silent(tmp_path, monkeypatch):
    script = tmp_path / "worker.py"
    script.write_text("# fictional worker\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 60)

    monkeypatch.setattr(run_mfl_correction_lane, "run_child", fake_run)
    assert not execute_stage(
        "train", [sys.executable, "-B", str(script)], output=tmp_path,
        environment=os.environ.copy(), completion=tmp_path / "none.json",
        validate=lambda _: True, timeout=60,
    )
    record = json.loads((tmp_path / "train.json").read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert record["error"] == "TimeoutExpired"
