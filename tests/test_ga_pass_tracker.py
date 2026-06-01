from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def test_true_ga_pass_tracker_counts_pass_19_through_51() -> None:
    report = GAPassTracker(project_root=ROOT).report().as_dict()
    assert report["status"] == "pass"
    assert report["total_true_ga_passes"] == 33
    assert report["true_ga_completed"] == 22
    assert report["true_ga_remaining"] == 11
    assert report["completed_passes"] == [19, 20, 21, 22, 23, 24, 25, 26, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45]
    assert report["remaining_passes"][0] == 27
    assert report["remaining_passes"][-1] == 51
    assert report["next_true_ga_pass"] == 27
    assert "configured exit evidence" in report["counting_rule"]


def test_tracker_config_marks_only_repo_evidence_backed_passes_complete() -> None:
    payload = json.loads((ROOT / "configs" / "maine_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    assert payload["current_true_ga_completed_passes"] == [19, 20, 21, 22, 23, 24, 25, 26, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45]
    complete = [row["pass"] for row in payload["passes"] if row["status"] == "complete"]
    assert complete == [19, 20, 21, 22, 23, 24, 25, 26, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45]


def test_report_ga_pass_count_script_summary() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "report-ga-pass-count.py"), "--summary"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "true_ga_remaining=11" in completed.stdout
    assert "true_ga_completed=22" in completed.stdout
    assert "next_pass=27" in completed.stdout
