from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pass32_38_engineering_evidence_runner_closes_repo_gates(tmp_path: Path) -> None:
    output = tmp_path / "pass32_38_engineering_evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-pass32-38-engineering-evidence.py"),
            "--output",
            str(output),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["passes_closed"] == [32, 33, 34, 35, 36, 37, 38]
    assert payload["attorney_reviewed"] is False
    assert payload["not_legal_signoff"] is True
    assert payload["pass_results"]["32"]["signals"]["structured_case_brief"] is True
    assert payload["pass_results"]["35"]["signals"]["cross_tenant_blocked"] is True
    assert payload["pass_results"]["38"]["signals"]["override_logged_without_silent_pass"] is True


def test_true_ga_tracker_marks_pass32_38_complete_without_closing_attorney_or_pilot_gates() -> None:
    tracker = json.loads((ROOT / "configs" / "maine_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    completed = tracker["current_true_ga_completed_passes"]
    for pass_number in range(32, 39):
        assert pass_number in completed
    for pass_number in [27, 28, 29, 30, 31, 46, 47, 48, 49, 50, 51]:
        assert pass_number not in completed
    rows = {row["pass"]: row for row in tracker["passes"]}
    assert all(rows[pass_number]["status"] == "complete" for pass_number in range(32, 39))
    assert rows[27]["next"] is True
