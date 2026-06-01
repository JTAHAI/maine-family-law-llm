from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.operator_release_eval import OperatorSourceBackedReleaseEvalRunner

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _measurement(name: str, value: float, sample_size: int = 500) -> dict:
    return {
        "name": name,
        "value": value,
        "sample_size": sample_size,
        "basis": "operator_source_backed_external_measurement",
        "operator_source_backed": True,
        "attorney_reviewed": False,
        "reviewer_status": "operator_source_backed",
    }


def _ready_roots(tmp_path: Path) -> tuple[Path, Path]:
    data_root = tmp_path / "ME_FM_LLM_data"
    eval_root = data_root / "eval_store"
    _write(
        data_root / "retrieval_smoke_report.json",
        {"status": "pass", "case_count": 500, "metrics": {"recall_at_20": 0.96}},
    )
    _write(data_root / "source_update_report.json", {"status": "pass", "freshness_audit_passed": True})
    _write(
        data_root / "release_metric_measurements.pass29.partial.json",
        {
            "release_metric_measurements": [
                _measurement("citation_existence", 0.995),
                _measurement("quote_span_verification", 0.98),
            ]
        },
    )
    _write(
        data_root / "release_metric_measurements.pass30.partial.json",
        {"release_metric_measurements": [_measurement("citation_support", 0.96)]},
    )
    _write(
        data_root / "release_metric_measurements.pass31.partial.json",
        {
            "release_metric_measurements": [
                _measurement("scope_verification", 1.0),
                _measurement("form_freshness_detection", 1.0),
            ]
        },
    )
    eval_root.mkdir(parents=True, exist_ok=True)
    return data_root, eval_root


def test_pass46_operator_source_backed_release_eval_can_pass_without_attorney_claim(tmp_path: Path) -> None:
    data_root, eval_root = _ready_roots(tmp_path)
    output = tmp_path / "pass46.json"
    measurements = tmp_path / "release_metric_measurements.operator.json"

    report = OperatorSourceBackedReleaseEvalRunner(project_root=ROOT).run(
        data_root=data_root,
        eval_root=eval_root,
        output_path=output,
        measurement_output_path=measurements,
    ).as_dict()

    assert report["status"] == "pass"
    assert report["operator_release_allowed"] is True
    assert report["true_ga_release_allowed"] is False
    assert report["attorney_reviewed"] is False
    assert report["legal_signoff"] is False
    assert report["pilot_signoff"] is False
    assert not report["blockers"]
    assert output.exists()
    emitted = json.loads(measurements.read_text(encoding="utf-8"))
    assert emitted["review_mode"] == "operator_source_backed"
    assert emitted["attorney_reviewed"] is False


def test_pass46_operator_source_backed_release_eval_blocks_missing_metrics(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    eval_root = data_root / "eval_store"
    eval_root.mkdir(parents=True)

    report = OperatorSourceBackedReleaseEvalRunner(project_root=ROOT).run(
        data_root=data_root,
        eval_root=eval_root,
    ).as_dict()

    assert report["status"] == "blocked"
    assert report["operator_release_allowed"] is False
    assert "missing_metric:citation_existence" in report["blockers"]
    assert "missing_metric:source_freshness_report_present" in report["blockers"]


def test_pass46_operator_source_backed_release_eval_cli_require_ready(tmp_path: Path) -> None:
    data_root, eval_root = _ready_roots(tmp_path)
    output = tmp_path / "cli-pass46.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-pass46-operator-source-backed-release-eval.py"),
            "--data-root",
            str(data_root),
            "--eval-root",
            str(eval_root),
            "--output",
            str(output),
            "--require-ready",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["operator_release_allowed"] is True
