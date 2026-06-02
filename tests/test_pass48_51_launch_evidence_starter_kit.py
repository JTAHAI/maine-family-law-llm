from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.pilot import LaunchEvidenceGate, build_launch_evidence_templates, write_launch_evidence_starter_kit

ROOT = Path(__file__).resolve().parents[1]


def test_pass48_51_templates_are_complete_and_default_blocked():
    templates = build_launch_evidence_templates()
    assert [template.pass_number for template in templates] == [48, 49, 50, 51]
    assert {template.root for template in templates} == {"pilot", "release"}
    assert all(template.payload["status"] == "blocked" for template in templates)
    assert all(template.payload["source"].startswith("external_") for template in templates)
    assert any(template.payload.get("real_matter_allowed") is False for template in templates)


def test_pass48_51_starter_kit_writes_templates_but_gate_still_blocks(tmp_path):
    manifest = write_launch_evidence_starter_kit(tmp_path)

    assert manifest["status"] == "blocked_templates_created"
    assert manifest["template_count"] == 4
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "pilot" / "attorney_sandbox_pilot_report.json").exists()
    assert (tmp_path / "release" / "ga_shipment_signoff.json").exists()

    report = LaunchEvidenceGate().audit(pilot_root=tmp_path / "pilot", release_root=tmp_path / "release").as_dict()
    blockers = "\n".join(report["blockers"])
    assert report["status"] == "blocked"
    assert report["closed_passes"] == []
    assert "pass48_artifact_status_not_ready:attorney_sandbox_pilot_report.json:blocked" in blockers
    assert "pass51_ga_shipped_must_be_true" in blockers


def test_pass48_51_starter_kit_cli_writes_manifest(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-pass48-51-launch-evidence-starter-kit.py",
            "--output-root",
            str(tmp_path / "kit"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_templates_created"
    assert (tmp_path / "kit" / "manifest.json").exists()
