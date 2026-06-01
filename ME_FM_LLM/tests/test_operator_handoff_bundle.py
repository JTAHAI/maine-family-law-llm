from pathlib import Path

from legal.ops import OperatorHandoffBundleBuilder, build_operator_handoff_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_operator_handoff_bundle_builds_with_expected_sections(tmp_path):
    report = OperatorHandoffBundleBuilder(ROOT, tmp_path / "ME_FM_LLM_data").build().as_dict()
    assert report["status"] == "pass"
    assert report["operator_test_battery_status"] == "pass"
    assert report["public_repo_readiness_status"] == "pass"
    assert report["networked_source_gate_status"] == "fail"
    assert "scripts/run-networked-source-gate.py" in report["script_hashes"]
    bundle = report["bundle"]
    assert "networked_source_gate" in bundle
    assert "operator_commands" in bundle
    assert bundle["public_github_staging"]["do_not_claim_legal_production_ready_from_fixture_tests"] is True


def test_operator_handoff_function_returns_dict(tmp_path):
    report = build_operator_handoff_bundle(ROOT, tmp_path / "ME_FM_LLM_data")
    assert report["status"] == "pass"
    assert any("run-operator-test-battery.py" in command for command in report["recommended_first_commands"])
