from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_tracker import GAPassTracker
from legal.security import LegalRedTeamRunner

ROOT = Path(__file__).resolve().parents[1]


def test_pass47_legal_red_team_engineering_evidence_passes() -> None:
    report = LegalRedTeamRunner(project_root=ROOT).run().as_dict()

    assert report["status"] == "pass"
    assert report["readiness"] == "legal_red_team_passed"
    assert report["no_filing_ready_bypass"] is True
    assert len(report["results"]) == len(report["required_categories"])
    assert all(row["safe"] for row in report["results"])


def test_pass47_closure_script_writes_non_attorney_non_pilot_evidence(tmp_path: Path) -> None:
    output = tmp_path / "pass47.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-pass47-red-team-closure-evidence.py"),
            "--require-ready",
            "--output",
            str(output),
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
    assert payload["completed_passes"] == [47]
    assert payload["attorney_reviewed"] is False
    assert payload["legal_signoff"] is False
    assert payload["pilot_signoff"] is False
    assert payload["no_filing_ready_bypass"] is True
    assert payload["case_count"] == payload["safe_case_count"] == 9


def test_pass47_reduces_tracker_count_without_closing_external_release_or_pilot_gates() -> None:
    report = GAPassTracker(project_root=ROOT).report().as_dict()

    assert report["status"] == "pass"
    assert report["true_ga_completed"] == 23
    assert report["true_ga_remaining"] == 10
    assert 47 in report["completed_passes"]
    for pass_number in [27, 28, 29, 30, 31, 46, 48, 49, 50, 51]:
        assert pass_number in report["remaining_passes"]
    assert report["next_true_ga_pass"] == 27
