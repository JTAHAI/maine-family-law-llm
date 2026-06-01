from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_gold_eval_pack_require_ready_exits_nonzero_for_seed_or_missing_gold(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit-gold-eval-pack.py"),
            "--eval-root",
            str(tmp_path),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    report = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert report["production_ready"] is False
    assert report["blockers"]


def test_release_metrics_require_ready_exits_nonzero_until_real_metrics_pass(tmp_path: Path) -> None:
    output = tmp_path / "release_metrics_evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-release-metrics-evidence.py"),
            "--eval-root",
            str(tmp_path),
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
    report = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert output.exists()
    assert report["release_gate_report"]["release_allowed"] is False
    assert report["readiness"] == "release_metrics_blocked_until_real_attorney_reviewed_gold_evidence"


def test_authority_harness_plan_can_make_gold_and_release_metrics_required(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-authority-data-product.py"),
            "--data-root",
            str(tmp_path / "data"),
            "--eval-root",
            str(tmp_path / "eval"),
            "--plan-only",
            "--require-gold-eval-pack",
            "--require-release-metrics",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    plan = json.loads(completed.stdout)
    by_name = {step["name"]: step for step in plan["steps"]}

    assert completed.returncode == 0
    assert by_name["build_gold_eval_pack_manifest"]["required"] is True
    assert by_name["audit_gold_eval_pack"]["required"] is True
    assert by_name["build_release_metrics_evidence"]["required"] is True
    assert "--require-ready" in by_name["audit_gold_eval_pack"]["command"]
    assert "--require-ready" in by_name["build_release_metrics_evidence"]["command"]
