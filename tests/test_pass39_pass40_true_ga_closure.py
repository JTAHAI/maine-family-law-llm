from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor
from legal.production.ga_pass_tracker import GAPassTracker
from legal.production.repo_ga_evidence import RepoGAEvidenceBuilder


ROOT = Path(__file__).resolve().parents[1]


def test_repo_ga_evidence_files_close_only_passes_39_and_40():
    result = RepoGAEvidenceBuilder(project_root=ROOT).build(write=False).as_dict()

    assert result["status"] == "pass", result
    assert result["completed_repo_only_passes"] == [39, 40]
    assert result["api_report"]["status"] == "pass"
    assert result["ui_report"]["status"] == "pass"
    assert result["api_report"]["production_legal_ga"] is False
    assert result["ui_report"]["production_legal_ga"] is False


def test_true_ga_tracker_now_has_four_evidence_backed_repo_passes_complete():
    report = GAPassTracker(project_root=ROOT).report().as_dict()

    assert report["status"] == "pass", report
    assert report["true_ga_completed"] == 4
    assert report["true_ga_remaining"] == 29
    assert report["completed_passes"] == [39, 40, 41, 42]
    assert report["next_true_ga_pass"] == 19


def test_ga_pass_evidence_audits_closed_repo_evidence_passes():
    report = GAPassEvidenceAuditor(project_root=ROOT).run().as_dict()

    assert report["status"] == "pass", report
    assert report["pass_evidence_valid"] is True
    assert report["audited_completed_passes"] == [39, 40, 41, 42]
    assert report["true_ga_remaining"] == 29
    assert not report["blockers"]


def test_generate_repo_ga_evidence_cli_check_mode():
    proc = subprocess.run(
        [sys.executable, "scripts/generate-repo-ga-evidence.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "pass"
    assert payload["completed_repo_only_passes"] == [39, 40]
