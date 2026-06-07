from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor
from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def test_pass43_pass45_split_reports_are_generated_and_counted(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-security-compliance-sre-evidence.py"),
            str(tmp_path / "sample.json"),
            "--ga-output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    for name in (
        "enterprise-security-test-report.json",
        "governance-compliance-packet-report.json",
        "sre-reliability-report.json",
    ):
        payload = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert payload["status"] == "pass", payload


def test_ga_tracker_now_counts_pass43_44_45_as_complete():
    report = GAPassTracker(project_root=ROOT).report().as_dict()
    assert {43, 44, 45}.issubset(set(report["completed_passes"]))
    assert report["true_ga_completed"] == 29
    assert report["true_ga_remaining"] == 4
    assert report["next_true_ga_pass"] == 48


def test_ga_evidence_audit_accepts_repo_pass43_44_45_reports():
    report = GAPassEvidenceAuditor(project_root=ROOT).run().as_dict()
    assert report["status"] == "pass", report
    assert {39, 40, 41, 42, 43, 44, 45}.issubset(set(report["audited_completed_passes"]))
    assert report["true_ga_remaining"] == 4
