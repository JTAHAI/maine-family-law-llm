from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from legal.release.git_safe_push import FOCUSED_PUSH_TESTS, PRE_PUSH_OUTPUT, run_git_safe_push

ROOT = Path(__file__).resolve().parents[1]


def _ok(stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def test_git_safe_push_is_no_op_safe_when_there_is_nothing_to_commit(monkeypatch) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        cmd = tuple(str(part) for part in command)
        commands.append(cmd)
        if cmd == ("git", "diff", "--cached", "--quiet"):
            return _ok()
        return _ok(stdout="ok")

    monkeypatch.setattr("legal.release.git_safe_push.subprocess.run", fake_run)

    report = run_git_safe_push(ROOT, message="No-op push test", branch="main", skip_tests=True)
    payload = report.as_dict()

    assert payload["status"] == "pass"
    assert payload["safe_to_push"] is True
    assert payload["production_legal_ready"] is False
    assert payload["no_changes_to_commit"] is True
    assert payload["commit_created"] is False
    assert payload["push_attempted"] is True
    assert ("git", "commit", "-m", "No-op push test") not in commands
    assert ("git", "push", "-u", "origin", "main") in commands
    commit_step = next(step for step in payload["steps"] if step["name"] == "git_commit")
    assert commit_step["status"] == "skipped"
    assert "No staged changes" in commit_step["stdout_tail"]


def test_git_safe_push_dry_run_does_not_commit_or_push_staged_changes(monkeypatch) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        cmd = tuple(str(part) for part in command)
        commands.append(cmd)
        if cmd == ("git", "diff", "--cached", "--quiet"):
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        return _ok(stdout="ok")

    monkeypatch.setattr("legal.release.git_safe_push.subprocess.run", fake_run)

    report = run_git_safe_push(
        ROOT,
        message="Dry run push test",
        branch="feature/test",
        skip_tests=True,
        dry_run=True,
    )
    payload = report.as_dict()

    assert payload["status"] == "pass"
    assert payload["no_changes_to_commit"] is False
    assert payload["commit_created"] is False
    assert payload["push_attempted"] is False
    assert ("git", "commit", "-m", "Dry run push test") not in commands
    assert ("git", "push", "-u", "origin", "feature/test") not in commands
    assert any(step["name"] == "git_commit" and step["status"] == "skipped" for step in payload["steps"])
    assert any(step["name"] == "git_push" and step["status"] == "skipped" for step in payload["steps"])


def test_git_safe_push_runs_the_public_source_gate_and_v192_focused_tests(monkeypatch) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        cmd = tuple(str(part) for part in command)
        commands.append(cmd)
        if cmd == ("git", "diff", "--cached", "--quiet"):
            return _ok()
        return _ok(stdout="ok")

    monkeypatch.setattr("legal.release.git_safe_push.subprocess.run", fake_run)

    report = run_git_safe_push(ROOT, message="Gate test", branch="main", skip_tests=False, dry_run=True)
    assert report.status == "pass"

    flattened = "\n".join(" ".join(command) for command in commands)
    assert "scripts/run-public-source-preflight.py" in flattened
    assert PRE_PUSH_OUTPUT in flattened
    for test_path in FOCUSED_PUSH_TESTS:
        assert test_path in flattened
    assert "tests/test_git_safe_push_v192.py" in flattened
