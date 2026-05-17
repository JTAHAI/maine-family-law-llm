from pathlib import Path

from legal.ops import LocalTestReadinessAuditor, run_local_test_readiness


ROOT = Path(__file__).resolve().parents[1]


def test_local_test_readiness_audit_passes_without_running_pytest(tmp_path):
    report = LocalTestReadinessAuditor(ROOT, tmp_path / "data").audit(run_pytest=False)
    as_dict = report.as_dict()
    assert as_dict["status"] == "pass"
    assert as_dict["ready_to_test_locally"] is True
    assert as_dict["public_github_source_ready"] is True
    assert as_dict["production_legal_ready"] is False
    assert as_dict["offline_validation_pack"]["fixture_only"] is True
    assert "networked_resource_collection_still_required_for_real_authority" in as_dict["warnings"]
    assert as_dict["production_legal_readiness_required_external_evidence"]


def test_run_local_test_readiness_helper_marks_pytest_skipped(tmp_path):
    report = run_local_test_readiness(ROOT, tmp_path / "data", run_pytest=False)
    assert report["status"] == "pass"
    assert report["pytest"]["status"] == "skipped"
    assert any("scripts\\run-test-readiness.py" in command for command in report["recommended_windows_test_commands"])
