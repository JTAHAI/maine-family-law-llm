from __future__ import annotations

from pathlib import Path

import pytest

from legal.release.wack_qualification import parse_wack_report


def _package(path: Path) -> None:
    path.write_bytes(b"fictional-msix-package")


def test_pass156_parses_hash_bound_wack_success_and_warnings(tmp_path: Path) -> None:
    package = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"; _package(package)
    output = tmp_path / "wack"; output.mkdir()
    (output / "report.xml").write_text('<Results><TestResult Id="manifest" Status="Pass">passed</TestResult><Warning Id="advisory">review before submission</Warning></Results>', encoding="utf-8")
    report = parse_wack_report(package=package, output_root=output, execution_status="completed")
    assert report["status"] == "pass" and report["report"]["warning_count"] == 1
    assert report["package"]["sha256"] and report["store_release_blocked"] is False


def test_pass156_blocks_not_run_missing_report_and_report_failures(tmp_path: Path) -> None:
    package = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"; _package(package)
    missing = parse_wack_report(package=package, output_root=tmp_path / "missing", execution_status="not_run", reason="elevation unavailable")
    assert missing["status"] == "blocked" and "wack_report_missing" in missing["blockers"]
    output = tmp_path / "wack"; output.mkdir()
    (output / "failure.xml").write_text('<Results><Failure Id="api">failed requirement</Failure></Results>', encoding="utf-8")
    failed = parse_wack_report(package=package, output_root=output, execution_status="completed")
    assert failed["status"] == "blocked" and "wack_failures_present" in failed["blockers"]


@pytest.mark.parametrize("contents", [
    "<Results />", "<Results><Message>completed</Message></Results>",
    '<Results><TestResult Status="NotRun"/></Results>',
    '<Results><TestResult Status="Pass"/><TestResult Status="Unknown"/></Results>',
    '<!DOCTYPE Results [<!ENTITY x "pass">]><Results>&x;</Results>',
])
def test_unknown_empty_or_incomplete_reports_do_not_qualify(tmp_path, contents):
    package = tmp_path / "fictional.msix"
    _package(package)
    output = tmp_path / "wack"
    output.mkdir()
    (output / "report.xml").write_text(contents, encoding="utf-8")
    result = parse_wack_report(package=package, output_root=output, execution_status="completed")
    assert result["status"] == "blocked"
    assert result["store_release_blocked"] is True


@pytest.mark.parametrize("contents", ['{}', '[]', '{"status":"pass","failures":[]}'])
def test_prior_json_summaries_cannot_certify_themselves(tmp_path, contents):
    package = tmp_path / "fictional.msix"
    _package(package)
    output = tmp_path / "wack"
    output.mkdir()
    (output / "wack-result.json").write_text(contents, encoding="utf-8")
    result = parse_wack_report(package=package, output_root=output, execution_status="completed")
    assert result["status"] == "blocked"
    assert "wack_report_missing" in result["blockers"]


def test_ambiguous_native_reports_fail_closed(tmp_path):
    package = tmp_path / "fictional.msix"
    _package(package)
    output = tmp_path / "wack"
    output.mkdir()
    for name in ("previous.xml", "current.xml"):
        (output / name).write_text('<Results><TestResult Status="Pass"/></Results>', encoding="utf-8")
    result = parse_wack_report(package=package, output_root=output, execution_status="completed")
    assert result["status"] == "blocked"
