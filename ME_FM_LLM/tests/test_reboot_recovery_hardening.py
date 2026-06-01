from pathlib import Path

from legal.ops import RebootRecoveryAuditor, run_reboot_recovery_healthcheck


ROOT = Path(__file__).resolve().parents[1]


def test_reboot_recovery_audit_passes_and_keeps_production_blocked(tmp_path):
    report = RebootRecoveryAuditor(ROOT, tmp_path / "ME_FM_LLM_data").audit()
    as_dict = report.as_dict()
    assert as_dict["status"] == "pass"
    assert as_dict["reboot_safe_for_local_testing"] is True
    assert as_dict["production_legal_ready"] is False
    assert as_dict["write_probe_ok"] is True
    assert as_dict["one_pass_log_only"] is True
    assert as_dict["txt_files"] == ["PASS_CHANGES.txt"]
    assert "scripts\\run-reboot-safe-healthcheck.py" in "\n".join(
        as_dict["after_reboot_windows_commands"]
    )
    assert as_dict["production_legal_readiness_remains_blocked_until"]


def test_reboot_recovery_helper_can_skip_write_probe(tmp_path):
    report = run_reboot_recovery_healthcheck(
        ROOT,
        tmp_path / "ME_FM_LLM_data",
        write_probe=False,
    )
    assert report["status"] == "pass"
    assert report["write_probe_ok"] is True
    assert any("collect-enterprise-resources.py" in command for command in report["networked_collection_commands"])


def test_reboot_recovery_blocks_data_root_inside_source_repo():
    report = RebootRecoveryAuditor(ROOT, ROOT / "runtime" / "bad_data_root").audit(
        create_external_dirs=False,
        write_probe=False,
    )
    assert report.status == "fail"
    assert "data_root_inside_source_repo" in report.blockers
