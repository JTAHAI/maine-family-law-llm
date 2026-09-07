from pathlib import Path

import pytest

from scripts.run_isolated_release_regression import audit_junit, junit_identity, partition_modules


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


def test_source_snapshot_preserves_dirty_bytes_without_copying_ignored_caches(
    tmp_path, monkeypatch
):
    from scripts import run_isolated_release_regression as runner

    root = tmp_path / "repository"
    output = root / "dist" / "qa"
    output.mkdir(parents=True)
    (root / "app.py").write_text("# fictional dirty source\n", encoding="utf-8")
    (root / "dist" / "ignored-model.bin").write_bytes(b"must not be copied")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **kw: b"app.py\0gone.py\0")
    snapshot, report = runner.snapshot_source(output)
    assert (snapshot / "app.py").read_bytes() == (root / "app.py").read_bytes()
    assert not (snapshot / "dist").exists()
    assert not (snapshot / "gone.py").exists()
    assert report["includes_uncommitted_source"] is True
    assert len(report["files"]) == 1 and len(report["tree_sha256"]) == 64
    (snapshot / "app.py").write_text("# changed test copy\n", encoding="utf-8")
    assert "dirty source" in (root / "app.py").read_text(encoding="utf-8")


def test_source_snapshot_refuses_outside_path_from_inventory(tmp_path, monkeypatch):
    from scripts import run_isolated_release_regression as runner

    root = tmp_path / "repository"
    output = root / "dist" / "qa"
    output.mkdir(parents=True)
    (tmp_path / "private.txt").write_text("fictional", encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **kw: b"../private.txt\0")
    with pytest.raises(ValueError, match="forbidden link or path"):
        runner.snapshot_source(output)


def test_windows_timeout_stops_only_owned_process_tree(monkeypatch):
    from types import SimpleNamespace

    from scripts import run_isolated_release_regression as runner

    calls = []
    waited = []
    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda command, **kw: (calls.append((command, kw)) or SimpleNamespace(returncode=0)),
    )
    process = SimpleNamespace(pid=123456, wait=lambda **kw: waited.append(kw))
    runner.stop_owned_test_process(process, {"TEMP": "fictional-repo-temp"})
    assert calls[0][0] == ["taskkill", "/PID", "123456", "/T", "/F"]
    assert calls[0][1]["env"] == {"TEMP": "fictional-repo-temp"}
    assert waited == [{"timeout": 15}]


def test_timeout_cleanup_failure_is_not_reported_as_clean(monkeypatch):
    from types import SimpleNamespace

    from scripts import run_isolated_release_regression as runner

    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1),
    )
    process = SimpleNamespace(pid=123456, poll=lambda: None)
    with pytest.raises(RuntimeError, match="Unable to stop"):
        runner.stop_owned_test_process(process, {})
