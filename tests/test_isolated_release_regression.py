from pathlib import Path

from scripts.run_isolated_release_regression import audit_junit, junit_identity, partition_modules
import pytest


def test_partition_preserves_every_test_once_and_keeps_modules_together():
    ids = ["tests/a.py::test_a", "tests/a.py::test_b", "tests/b.py::test_c"]
    batches = partition_modules(ids, 2)
    assert batches == [ids[:2], ids[2:]]
    assert [node for batch in batches for node in batch] == ids


def test_identity_preserves_parametrized_ids_with_colons():
    assert junit_identity("tests/a.py::Suite::test_a[path::one]") == (
        "tests.a.Suite",
        "test_a[path::one]",
    )


def test_evidence_rejects_omitted_and_duplicate_cases(tmp_path: Path):
    xml = tmp_path / "batch.xml"
    xml.write_text(
        '<testsuites><testsuite><testcase classname="tests.a" name="test_a"/>'
        '<testcase classname="tests.a" name="test_a"/></testsuite></testsuites>'
    )
    result = audit_junit(xml, ["tests/a.py::test_a", "tests/a.py::test_b"])
    assert not result["coverage_matches_collection"]


def test_evidence_retains_failed_and_skipped_results(tmp_path: Path):
    xml = tmp_path / "batch.xml"
    xml.write_text(
        '<testsuites><testsuite><testcase classname="tests.a" name="test_a">'
        '<failure/></testcase><testcase classname="tests.a" name="test_b">'
        '<skipped message="Windows only"/></testcase></testsuite></testsuites>'
    )
    result = audit_junit(xml, ["tests/a.py::test_a", "tests/a.py::test_b"])
    assert result["coverage_matches_collection"]
    assert result["failed_or_error"] == 1 and result["skipped"] == 1 and result["passed"] == 0
    assert result["skip_reasons"][0]["reason"] == "Windows only"


def test_fixture_factory_never_uses_the_repository_parent(tmp_path, monkeypatch):
    from scripts import run_isolated_release_regression as runner
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    output = tmp_path / "dist" / "report"
    output.mkdir(parents=True)
    calls = []
    monkeypatch.setattr(runner.tempfile, "TemporaryDirectory", lambda **kw: calls.append(kw))
    runner.fixture_workspace(output)
    assert calls == [{"prefix": "fixtures-", "dir": output.resolve()}]


def test_fixture_factory_rejects_external_storage(tmp_path, monkeypatch):
    from scripts import run_isolated_release_regression as runner
    monkeypatch.setattr(runner, "ROOT", tmp_path / "project")
    with pytest.raises(ValueError, match="repository dist"):
        runner.fixture_workspace(tmp_path)
