from pathlib import Path

from legal.ops import OperatorTestBatteryAuditor, run_operator_test_battery


ROOT = Path(__file__).resolve().parents[1]


def test_operator_test_battery_passes_for_local_source_testing(tmp_path):
    report = OperatorTestBatteryAuditor(ROOT, tmp_path / "ME_FM_LLM_data").audit()
    as_dict = report.as_dict()
    assert as_dict["status"] == "pass"
    assert as_dict["ready_for_operator_local_test"] is True
    assert as_dict["production_legal_ready"] is False
    assert as_dict["missing_required_repo_files"] == []
    assert any("run-quality-checks.py" in command for command in as_dict["local_operator_commands"])
    assert as_dict["production_legal_readiness_blockers"]


def test_operator_test_battery_blocks_data_root_inside_repo():
    report = run_operator_test_battery(
        ROOT,
        ROOT / "runtime" / "bad_operator_data_root",
        create_external_dirs=False,
        write_probe=False,
    )
    assert report["status"] == "fail"
    assert "data_root_inside_source_repo" in report["blockers"]
