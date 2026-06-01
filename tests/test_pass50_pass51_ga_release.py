from pathlib import Path

from legal.release import (
    GAShipmentAuditor,
    ReleaseBlocker,
    ReleaseCandidateAuditor,
    ReleaseSignoff,
    build_approved_signoff_fixture,
    build_ga_control_fixture,
    build_release_artifact_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.18.0-pass50-pass51-ga-release-controls"


def test_pass50_release_candidate_passes_with_artifacts_signoffs_and_no_p0_p1():
    rc_artifacts, _ = build_release_artifact_fixture(VERSION)
    report = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=VERSION,
        artifacts=rc_artifacts,
        signoffs=build_approved_signoff_fixture(),
        blockers=[],
        audit_enterprise_readiness_status="pass",
    ).as_dict()

    assert report["status"] == "pass"
    assert report["release_candidate_frozen"] is True
    assert report["source_repo_clean"] is True
    assert report["audit_enterprise_readiness_status"] == "pass"
    assert not report["open_p0_p1_blockers"]
    assert report["artifact_inventory_hash"]


def test_pass50_blocks_missing_signoff_failed_readiness_and_open_p1():
    rc_artifacts, _ = build_release_artifact_fixture(VERSION)
    signoffs = [s for s in build_approved_signoff_fixture() if s.role != "legal"]
    signoffs.append(ReleaseSignoff("ops", "ops-owner", "rejected", "2026-05-16T00:00:00Z"))
    report = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=VERSION,
        artifacts=rc_artifacts[:-1],
        signoffs=signoffs,
        blockers=[ReleaseBlocker("P1-real-pilot-evidence", "P1", "open")],
        audit_enterprise_readiness_status="blocked",
    ).as_dict()
    blockers = "\n".join(report["blockers"])

    assert report["status"] == "blocked"
    assert report["release_candidate_frozen"] is False
    assert "missing_artifact:release_notes" in blockers
    assert "missing_signoff:legal" in blockers
    assert "signoff_not_approved:ops" in blockers
    assert "open_P1_blocker:P1-real-pilot-evidence" in blockers
    assert "audit_enterprise_readiness_not_pass" in blockers


def test_pass51_ga_shipment_passes_with_release_candidate_artifacts_and_controls():
    rc_artifacts, ga_artifacts = build_release_artifact_fixture(VERSION)
    release_candidate = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=VERSION,
        artifacts=rc_artifacts,
        signoffs=build_approved_signoff_fixture(),
        audit_enterprise_readiness_status="pass",
    )
    report = GAShipmentAuditor().audit(
        version=VERSION,
        release_candidate_report=release_candidate,
        artifacts=ga_artifacts,
        controls=build_ga_control_fixture(),
    ).as_dict()

    assert report["status"] == "pass"
    assert report["ga_shipped"] is True
    assert report["release_candidate_status"] == "pass"
    assert report["maintenance_operations_ready"] is True
    assert report["shipment_manifest_hash"]


def test_pass51_blocks_if_release_candidate_or_ga_definition_controls_missing():
    rc_artifacts, ga_artifacts = build_release_artifact_fixture(VERSION)
    blocked_candidate = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=VERSION,
        artifacts=rc_artifacts,
        signoffs=build_approved_signoff_fixture(),
        blockers=[ReleaseBlocker("P0-security", "P0", "open")],
    )
    controls = build_ga_control_fixture()
    controls["uses_real_official_maine_authority"] = False
    controls["attorney_reviewed_evals_present"] = False
    report = GAShipmentAuditor().audit(
        version=VERSION,
        release_candidate_report=blocked_candidate,
        artifacts=ga_artifacts[:-1],
        controls=controls,
    ).as_dict()
    blockers = "\n".join(report["blockers"])

    assert report["status"] == "blocked"
    assert report["ga_shipped"] is False
    assert "release_candidate_not_frozen_or_not_passed" in blockers
    assert "missing_ga_artifact:model_update_runbook" in blockers
    assert "ga_control_not_satisfied:uses_real_official_maine_authority" in blockers
    assert "ga_control_not_satisfied:attorney_reviewed_evals_present" in blockers
