from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.pilot import LaunchEvidenceGate

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pass48_51_launch_evidence_gate_blocks_missing_external_artifacts(tmp_path):
    report = LaunchEvidenceGate().audit(pilot_root=tmp_path / "pilot", release_root=tmp_path / "release").as_dict()

    assert report["status"] == "blocked"
    assert report["open_passes"] == [48, 49, 50, 51]
    blockers = "\n".join(report["blockers"])
    assert "pass48_missing_artifact:attorney_sandbox_pilot_report.json" in blockers
    assert "pass49_missing_artifact:limited_real_matter_pilot_report.json" in blockers
    assert "pass50_missing_artifact:ga_release_candidate_signoff.json" in blockers
    assert "pass51_missing_artifact:ga_shipment_signoff.json" in blockers


def test_pass48_51_launch_evidence_gate_passes_with_explicit_external_ready_files(tmp_path):
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", {"status": "pass", "source": "external_pilot"})
    _write(pilot / "limited_real_matter_pilot_report.json", {"status": "pass", "source": "external_pilot"})
    _write(release / "ga_release_candidate_signoff.json", {"status": "signed", "source": "external_release"})
    _write(release / "ga_shipment_signoff.json", {"status": "pass", "source": "external_release"})

    report = LaunchEvidenceGate().audit(pilot_root=pilot, release_root=release).as_dict()

    assert report["status"] == "pass"
    assert report["closed_passes"] == [48, 49, 50, 51]
    assert report["open_passes"] == []
    assert report["readiness"] == "pass48_51_launch_evidence_ready"
    assert all(item["sha256"] for item in report["artifacts"])


def test_pass48_51_launch_evidence_gate_blocks_rejected_or_non_json_artifacts(tmp_path):
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", {"status": "pass"})
    _write(pilot / "limited_real_matter_pilot_report.json", {"status": "blocked"})
    _write(release / "ga_release_candidate_signoff.json", {"status": "rejected"})
    (release / "ga_shipment_signoff.json").parent.mkdir(parents=True, exist_ok=True)
    (release / "ga_shipment_signoff.json").write_text("not json", encoding="utf-8")

    report = LaunchEvidenceGate().audit(pilot_root=pilot, release_root=release).as_dict()
    blockers = "\n".join(report["blockers"])

    assert report["status"] == "blocked"
    assert report["closed_passes"] == [48]
    assert report["open_passes"] == [49, 50, 51]
    assert "pass49_artifact_status_not_ready:limited_real_matter_pilot_report.json:blocked" in blockers
    assert "pass50_artifact_status_not_ready:ga_release_candidate_signoff.json:rejected" in blockers
    assert "pass51_artifact_not_json:ga_shipment_signoff.json" in blockers


def test_pass48_51_launch_evidence_cli_writes_report_and_fail_closed(tmp_path):
    output = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-pass48-51-launch-evidence-gates.py",
            "--pilot-root",
            str(tmp_path / "pilot"),
            "--release-root",
            str(tmp_path / "release"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert "pass48_missing_artifact:attorney_sandbox_pilot_report.json" in payload["blockers"]
    assert "pass48_51_launch_evidence_blocked" in result.stdout
