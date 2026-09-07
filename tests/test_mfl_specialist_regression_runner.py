import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_mfl_specialist_regression import FIXTURES, MINIMUM_FROZEN_CASES, evaluator

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_suite_inventory_is_explicit_and_has_no_duplicates():
    assert len(FIXTURES["drafting"]) == 2
    assert len(FIXTURES["evidence_review"]) == 8
    for values in FIXTURES.values():
        assert len(values) == len(set(values))
        assert all(value.endswith(".json") for value in values)
    assert MINIMUM_FROZEN_CASES == {"drafting": 22, "evidence_review": 104}


def test_capability_selects_only_its_owned_evaluator(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    practical = scripts / "evaluate_mfl_practical_research_v2.py"
    evidence = scripts / "evaluate_mfl_evidence_research_v2.py"
    practical.touch()
    evidence.touch()
    assert evaluator(tmp_path, "drafting") == practical.resolve()
    assert evaluator(tmp_path, "evidence_review") == evidence.resolve()


def test_regression_runner_is_directly_executable():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_mfl_specialist_regression.py"), "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert "--capability" in completed.stdout


def test_fixture_changes_before_inference_cannot_redefine_success(tmp_path, monkeypatch):
    from scripts import run_mfl_specialist_regression as runner
    from scripts.summarize_mfl_specialist_quality import sha256_file

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "FIXTURES", {"drafting": ("fictional.json",)})
    fixtures = tmp_path / "data/evaluation"
    fixtures.mkdir(parents=True)
    (tmp_path / "configs").mkdir()
    (tmp_path / "scripts").mkdir()
    fixture = fixtures / "fictional.json"
    fixture.write_text(json.dumps({"cases": [{"id": "fictional-check"}]}))
    evaluator_path = tmp_path / "scripts/evaluate_mfl_practical_research_v2.py"
    evaluator_path.write_text("# fictional evaluator")
    baseline = {
        "schema_version": "mfl_specialist_regression_baseline_v1",
        "evaluators": {evaluator_path.name: sha256_file(evaluator_path)},
        "fixtures": {
            fixture.name: {"sha256": sha256_file(fixture), "case_ids": ["fictional-check"]}
        },
    }
    (tmp_path / "configs/mfl_specialist_regression_baseline.json").write_text(json.dumps(baseline))
    assert len(runner.verify_regression_baseline(tmp_path, "drafting")) == 64
    fixture.write_text(json.dumps({"cases": []}))
    with pytest.raises(ValueError, match="fixture_not_pinned"):
        runner.verify_regression_baseline(tmp_path, "drafting")


def test_evaluator_output_capture_is_bounded_and_timeout_stops_owned_process(tmp_path):
    from scripts.bounded_evaluation_process import run_bounded

    output = run_bounded(
        [sys.executable, "-c", "print('x' * 200000)"],
        cwd=tmp_path,
        env=os.environ.copy(),
        timeout_seconds=15,
        tail_bytes=512,
    )
    assert output["returncode"] == 0
    assert len(output["output_tail"].encode()) <= 512
    assert not output["cleanup_failed"]
    stalled = run_bounded(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=tmp_path,
        env=os.environ.copy(),
        timeout_seconds=1,
    )
    assert stalled["timed_out"]
    assert stalled["returncode"] is not None
    assert not stalled["cleanup_failed"]
