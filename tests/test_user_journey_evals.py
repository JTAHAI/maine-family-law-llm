from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.user_journey_eval import UserJourneyEvalRunner


ROOT = Path(__file__).resolve().parents[1]


def test_user_journey_eval_runner_passes_all_demo_cases() -> None:
    report = UserJourneyEvalRunner(project_root=ROOT).run().as_dict()
    assert report["status"] == "pass"
    assert report["case_count"] >= 15
    assert all(value == 1.0 for value in report["metrics"].values())
    assert report["hard_safety_checks"]["prompt_injection_resistance"] is True


def test_user_journey_eval_script_outputs_deterministic_json(tmp_path: Path) -> None:
    output = tmp_path / "journey-report.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run-user-journey-evals.py"), str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert output.is_file()
