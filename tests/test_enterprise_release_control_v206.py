from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.release.enterprise_release_control_v206 import (
    PACKET_SCHEMA,
    VERSION,
    build_enterprise_release_packet,
    render_enterprise_release_html,
    write_evidence_outputs,
)

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _pass48_payload() -> dict:
    return {
        "status": "pass",
        "source": "external_pilot",
        "signed_by": "maine-attorney-reviewer",
        "signed_at": "2026-06-05T00:00:00Z",
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
        "signed_at": "2026-06-05T00:00:00Z",
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
        "signed_at": "2026-06-05T00:00:00Z",
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
        "signed_at": "2026-06-05T00:00:00Z",
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


def test_v206_enterprise_release_control_blocks_missing_external_evidence() -> None:
    packet = build_enterprise_release_packet()

    assert packet["schema"] == PACKET_SCHEMA
    assert packet["version"] == VERSION
    assert packet["enterprise_ready"] is False
    assert packet["production_legal_ready"] is False
    assert packet["ga_shipped"] is False
    assert packet["remaining_passes"] == [48, 49, 50, 51]
    assert packet["launch_gate_report"]["status"] == "blocked"
    assert "enterprise_release_blocked_until_pass48_51_external_evidence_passes" in packet["release_blockers"]
    assert packet["legal_safety_defaults"]["filing_ready_by_default"] is False


def test_v206_external_evidence_checklist_is_complete_and_private_safe() -> None:
    packet = build_enterprise_release_packet()
    checklist = packet["external_evidence_checklist"]

    assert [row["pass"] for row in checklist] == [48, 49, 50, 51]
    assert all(row["must_be_external"] for row in checklist)
    assert all(row["private_data_allowed"] is False for row in checklist)
    pass50 = next(row for row in checklist if row["pass"] == 50)
    pass51 = next(row for row in checklist if row["pass"] == 51)
    assert pass50["required_signoff_roles"] == ["security", "legal", "product", "ops"]
    assert "uses_real_official_maine_authority" in pass51["required_controls"]


def test_v206_can_become_enterprise_ready_only_with_explicit_external_artifacts(tmp_path: Path) -> None:
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", _pass48_payload())
    _write(pilot / "limited_real_matter_pilot_report.json", _pass49_payload())
    _write(release / "ga_release_candidate_signoff.json", _pass50_payload())
    _write(release / "ga_shipment_signoff.json", _pass51_payload())

    packet = build_enterprise_release_packet(pilot_root=pilot, release_root=release)

    assert packet["launch_gate_report"]["status"] == "pass"
    assert packet["remaining_passes"] == []
    assert packet["closed_launch_passes"] == [48, 49, 50, 51]
    assert packet["enterprise_ready"] is True
    assert packet["production_legal_ready"] is True
    assert packet["ga_shipped"] is True


def test_v206_blocks_placeholder_or_partial_external_artifacts(tmp_path: Path) -> None:
    pilot = tmp_path / "pilot"
    release = tmp_path / "release"
    _write(pilot / "attorney_sandbox_pilot_report.json", {"status": "pass"})
    _write(pilot / "limited_real_matter_pilot_report.json", {"status": "pass"})
    _write(release / "ga_release_candidate_signoff.json", {"status": "signed"})
    _write(release / "ga_shipment_signoff.json", {"status": "pass"})

    packet = build_enterprise_release_packet(pilot_root=pilot, release_root=release)
    blockers = "\n".join(packet["release_blockers"])

    assert packet["enterprise_ready"] is False
    assert packet["production_legal_ready"] is False
    assert "pass48_attorney_reviewer_count_must_be_at_least_1" in blockers
    assert "pass49_matter_count_must_be_at_least_1" in blockers
    assert "pass50_artifact_inventory_hash_missing" in blockers
    assert "pass51_shipment_manifest_hash_missing" in blockers


def test_v206_html_contains_enterprise_release_markers() -> None:
    html = render_enterprise_release_html(build_enterprise_release_packet())

    for marker in (
        "Enterprise Release Control",
        "enterprise_ready=false",
        "production_legal_ready=false",
        "ga_shipped=false",
        "Pass 48",
        "Pass 51",
        "release-blocker-card",
        "external-evidence-checklist",
        "Ask",
        "Audit",
        "Ship",
    ):
        assert marker in html


def test_v206_evidence_outputs_are_valid_and_blocked_by_default(tmp_path: Path) -> None:
    outputs = write_evidence_outputs(tmp_path)

    packet = json.loads(Path(outputs["packet"]).read_text(encoding="utf-8"))
    audit = json.loads(Path(outputs["audit"]).read_text(encoding="utf-8"))
    summary = json.loads(Path(outputs["test_summary"]).read_text(encoding="utf-8"))
    html = Path(outputs["html"]).read_text(encoding="utf-8")

    assert packet["schema"] == PACKET_SCHEMA
    assert packet["enterprise_ready"] is False
    assert audit["status"] == "pass"
    assert summary["status"] == "pass"
    assert "Enterprise Release Control" in html


def test_v206_evidence_script_generates_required_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-enterprise-release-control-evidence.py",
            "--output-dir",
            str(tmp_path),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["enterprise_ready"] is False
    assert set(payload["outputs"]) == {"packet", "audit", "html", "test_summary"}


def test_v206_forbidden_release_claims_are_explicit() -> None:
    packet = build_enterprise_release_packet()
    forbidden = packet["forbidden_release_claims"]

    assert "production_legal_ready_without_external_evidence" in forbidden
    assert "ga_shipped_without_external_shipment_manifest_and_all_controls" in forbidden
    assert packet["claims"]["private_data_packaged"] is False
