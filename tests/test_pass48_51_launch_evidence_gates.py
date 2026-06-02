from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.pilot import LaunchEvidenceGate

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _pass48_payload() -> dict:
    return {
        "status": "pass",
        "source": "external_pilot",
        "signed_by": "maine-attorney-reviewer",
        "signed_at": "2026-06-02T00:00:00Z",
        "attorney_reviewer_count": 1,
        "bar_status_verified": True,
        "training_complete": True,
        "real_matter_allowed": False,
        "critical_open_count": 0,
        "feedback_queue_reviewed": True,
    }


def _pass49_payload() -> dict:
    return {
        "status": "pass",
        "source": "external_pilot",
        "signed_by": "pilot-owner",
        "signed_at": "2026-06-02T00:00:00Z",
        "matter_count": 1,
        "all_matters_have_explicit_consent": True,
        "tenant_isolation_verified": True,
        "encrypted_storage_verified": True,
        "human_review_completed": True,
        "attorney_signoff_complete": True,
        "daily_review_complete": True,
        "training_use_allowed": False,
        "data_leakage_count": 0,
        "unsupported_export_attempt_count": 0,
        "open_incident_count": 0,
    }


def _pass50_payload() -> dict:
    return {
        "status": "signed",
        "source": "external_release",
        "signed_by": "release-manager",
        "signed_at": "2026-06-02T00:00:00Z",
        "release_candidate_frozen": True,
        "open_p0_p1_count": 0,
        "artifact_inventory_hash": "sha256:external-release-inventory",
        "signoffs": [
            {"role": "security", "status": "approved"},
            {"role": "legal", "status": "approved"},
            {"role": "product", "status": "approved"},
            {"role": "ops", "status": "approved"},
        ],
    }


def _pass51_payload() -> dict:
    return {
        "status": "pass",
        "source": "external_release",
        "signed_by": "ga-owner",
        "signed_at": "2026-06-02T00:00:00Z",
        "ga_shipped": True,
        "release_candidate_status": "pass",
        "shipment_manifest_hash": "sha256:external-shipment-manifest",
        "controls": {
            "runs_from_clean_deployment": True,
            "uses_real_official_maine_authority": True,
            "attorney_reviewed_evals_present": True,
            "release_metrics_pass": True,
            "unsupported_filing_ready_output_blocked": True,
            "private_matter_data_protected": True,
            "audit_trails_present": True,
            "security_controls_present": True,
            "pilot_evidence_present": True,
            "rollback_and_maintenance_operations_present": True,
        },
    }


def test_pass48_51_launch_evidence_gate_blocks_missing_external_artifacts(tmp_path):
    report = LaunchEvidenceGate().audit(pilot_root=tmp_path / "pilot", release_root=tmp_path / "release").as_dict()

    assert report["status"] == "blocked"
    assert report["open_passes"] == [48, 49, 50, 51]
    blockers = "\n".join(report["blockers"])
    assert "pass48_missing_artifact:attorney_sandbox_pilot_report.json" in blockers
    assert "pass49_missing_artifact:limited_real_matter_pilot_report.json" in blockers
    assert "pass50_missing_artifact:ga_release_candidate_signoff.json" in blockers
    assert "pass51_missing_artifact:ga_shipment_signoff.json" in blockers


def test_pass48_51_launch_evidence_gate_blocks_placeholder_pass_files(tmp_path):
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", {"status": "pass"})
    _write(pilot / "limited_real_matter_pilot_report.json", {"status": "pass"})
    _write(release / "ga_release_candidate_signoff.json", {"status": "signed"})
    _write(release / "ga_shipment_signoff.json", {"status": "pass"})

    report = LaunchEvidenceGate().audit(pilot_root=pilot, release_root=release).as_dict()
    blockers = "\n".join(report["blockers"])

    assert report["status"] == "blocked"
    assert report["closed_passes"] == []
    assert "pass48_attorney_reviewer_count_must_be_at_least_1" in blockers
    assert "pass49_matter_count_must_be_at_least_1" in blockers
    assert "pass50_artifact_inventory_hash_missing" in blockers
    assert "pass51_shipment_manifest_hash_missing" in blockers


def test_pass48_51_launch_evidence_gate_passes_with_explicit_external_ready_files(tmp_path):
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", _pass48_payload())
    _write(pilot / "limited_real_matter_pilot_report.json", _pass49_payload())
    _write(release / "ga_release_candidate_signoff.json", _pass50_payload())
    _write(release / "ga_shipment_signoff.json", _pass51_payload())

    report = LaunchEvidenceGate().audit(pilot_root=pilot, release_root=release).as_dict()

    assert report["status"] == "pass"
    assert report["closed_passes"] == [48, 49, 50, 51]
    assert report["open_passes"] == []
    assert report["readiness"] == "pass48_51_launch_evidence_ready"
    assert all(item["sha256"] for item in report["artifacts"])


def test_pass48_51_launch_evidence_gate_blocks_rejected_or_non_json_artifacts(tmp_path):
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", _pass48_payload())
    bad49 = _pass49_payload() | {"status": "blocked", "data_leakage_count": 1}
    bad50 = _pass50_payload() | {"status": "rejected", "open_p0_p1_count": 1}
    _write(pilot / "limited_real_matter_pilot_report.json", bad49)
    _write(release / "ga_release_candidate_signoff.json", bad50)
    _write(release / "ga_shipment_signoff.json", "not json")

    report = LaunchEvidenceGate().audit(pilot_root=pilot, release_root=release).as_dict()
    blockers = "\n".join(report["blockers"])

    assert report["status"] == "blocked"
    assert report["closed_passes"] == [48]
    assert report["open_passes"] == [49, 50, 51]
    assert "pass49_artifact_status_not_ready:limited_real_matter_pilot_report.json:blocked" in blockers
    assert "pass49_data_leakage_count_must_be_zero" in blockers
    assert "pass50_artifact_status_not_ready:ga_release_candidate_signoff.json:rejected" in blockers
    assert "pass50_open_p0_p1_count_must_be_zero" in blockers
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
