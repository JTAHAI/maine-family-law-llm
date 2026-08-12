from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

FOCUSED_PUSH_TESTS = (
    "tests/test_public_source_pre_push_gate_v191.py",
    "tests/test_git_safe_push_v192.py",
    "tests/test_pass48_51_launch_evidence_gates.py",
    "tests/test_pass48_51_launch_evidence_starter_kit.py",
    "tests/test_enterprise_release_control_v206.py",
    "tests/test_attorney_sandbox_review_kit_v193.py",
    "tests/test_chat_library_v187_input_clear_and_routing.py",
    "tests/test_best_interest_chat_answer.py",
    "tests/test_public_repo_integrity.py",
)

PRE_PUSH_OUTPUT = "docs/external-evidence/public_source_pre_push_gate_v193.json"


@dataclass(frozen=True)
class GitSafePushStep:
    name: str
    command: tuple[str, ...]
    returncode: int
    status: str
    stdout_tail: str = ""
    stderr_tail: str = ""
    skipped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "returncode": self.returncode,
            "status": self.status,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class GitSafePushReport:
    schema: str
    status: str
    safe_to_push: bool
    production_legal_ready: bool
    project_root: str
    generated_at: str
    branch: str
    message: str
    dry_run: bool
    skip_tests: bool
    no_changes_to_commit: bool
    commit_created: bool
    push_attempted: bool
    steps: tuple[GitSafePushStep, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    interpretation: str = (
        "This wrapper verifies source hygiene before pushing public source code. It does not claim legal GA readiness, attorney review, pilot completion, or filing-ready output."
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "safe_to_push": self.safe_to_push,
            "production_legal_ready": self.production_legal_ready,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "branch": self.branch,
            "message": self.message,
            "dry_run": self.dry_run,
            "skip_tests": self.skip_tests,
            "no_changes_to_commit": self.no_changes_to_commit,
            "commit_created": self.commit_created,
            "push_attempted": self.push_attempted,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "interpretation": self.interpretation,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:] if text else ""


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    name: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> GitSafePushStep:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    status = "pass" if result.returncode == 0 else "fail"
    step = GitSafePushStep(
        name=name,
        command=tuple(command),
        returncode=result.returncode,
        status=status,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}: {result.stderr or result.stdout}")
    return step


def _python_command(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


def _focused_tests() -> tuple[str, ...]:
    return _python_command("-m", "pytest", *FOCUSED_PUSH_TESTS, "-q")


def _blocked_report(
    *,
    root: Path,
    branch: str,
    message: str,
    dry_run: bool,
    skip_tests: bool,
    steps: list[GitSafePushStep],
    blocker: str,
) -> GitSafePushReport:
    return GitSafePushReport(
        schema="maine_family_law_llm.git_safe_push.v1",
        status="fail",
        safe_to_push=False,
        production_legal_ready=False,
        project_root=str(root),
        generated_at=_utc_now(),
        branch=branch,
        message=message,
        dry_run=dry_run,
        skip_tests=skip_tests,
        no_changes_to_commit=False,
        commit_created=False,
        push_attempted=False,
        steps=tuple(steps),
        blockers=(blocker,),
    )


def run_git_safe_push(
    repo_root: str | Path = ".",
    *,
    message: str = "Run public-source pre-push gate",
    branch: str = "main",
    skip_tests: bool = False,
    dry_run: bool = False,
) -> GitSafePushReport:
    """Run the tested safe-push sequence.

    The wrapper is intentionally no-op safe: after staging, it checks
    `git diff --cached --quiet`. A clean tree skips `git commit` instead of
    failing with Git's "nothing to commit" exit code.
    """

    root = Path(repo_root).resolve()
    steps: list[GitSafePushStep] = []
    env = None

    try:
        steps.append(
            _run(
                _python_command("scripts/clean-local-artifacts.py", "--repo-root", ".", "--include-venv", "--json"),
                cwd=root,
                name="clean_local_artifacts",
                env=env,
            )
        )
        steps.append(
            _run(
                _python_command("scripts/doctor-local-repo.py", "--repo-root", ".", "--json"),
                cwd=root,
                name="local_doctor",
                env=env,
            )
        )
        steps.append(
            _run(
                _python_command(
                    "scripts/run-public-source-preflight.py",
                    "--repo-root",
                    ".",
                    "--require-ready",
                    "--output",
                    PRE_PUSH_OUTPUT,
                ),
                cwd=root,
                name="public_source_preflight",
                env=env,
            )
        )
        if skip_tests:
            steps.append(
                GitSafePushStep(
                    name="focused_tests",
                    command=_focused_tests(),
                    returncode=0,
                    status="skipped",
                    skipped=True,
                    stdout_tail="Skipped by operator switch.",
                )
            )
        else:
            steps.append(_run(_focused_tests(), cwd=root, name="focused_tests", env=env))

        steps.append(_run(("git", "status", "--short"), cwd=root, name="git_status_before_stage", env=env))
        steps.append(_run(("git", "add", "-A"), cwd=root, name="git_add_all", env=env))
        diff_step = _run(
            ("git", "diff", "--cached", "--quiet"),
            cwd=root,
            name="git_diff_cached_quiet",
            check=False,
            env=env,
        )
        steps.append(diff_step)
        no_changes_to_commit = diff_step.returncode == 0
        commit_created = False
        push_attempted = False

        if no_changes_to_commit:
            steps.append(
                GitSafePushStep(
                    name="git_commit",
                    command=("git", "commit", "-m", message),
                    returncode=0,
                    status="skipped",
                    skipped=True,
                    stdout_tail="No staged changes; skipping commit.",
                )
            )
        else:
            if dry_run:
                steps.append(
                    GitSafePushStep(
                        name="git_commit",
                        command=("git", "commit", "-m", message),
                        returncode=0,
                        status="skipped",
                        skipped=True,
                        stdout_tail="Dry run; commit not created.",
                    )
                )
            else:
                steps.append(
                    _run(("git", "commit", "-m", message), cwd=root, name="git_commit", env=env)
                )
                commit_created = True

        if dry_run:
            steps.append(
                GitSafePushStep(
                    name="git_push",
                    command=("git", "push", "-u", "origin", branch),
                    returncode=0,
                    status="skipped",
                    skipped=True,
                    stdout_tail="Dry run; push not attempted.",
                )
            )
        else:
            push_attempted = True
            steps.append(_run(("git", "push", "-u", "origin", branch), cwd=root, name="git_push", env=env))

        return GitSafePushReport(
            schema="maine_family_law_llm.git_safe_push.v1",
            status="pass",
            safe_to_push=True,
            production_legal_ready=False,
            project_root=str(root),
            generated_at=_utc_now(),
            branch=branch,
            message=message,
            dry_run=dry_run,
            skip_tests=skip_tests,
            no_changes_to_commit=no_changes_to_commit,
            commit_created=commit_created,
            push_attempted=push_attempted,
            steps=tuple(steps),
            blockers=(),
        )
    except Exception as exc:  # pragma: no cover - exercised through CLI failure paths locally
        return _blocked_report(
            root=root,
            branch=branch,
            message=message,
            dry_run=dry_run,
            skip_tests=skip_tests,
            steps=steps,
            blocker=f"git_safe_push_failed:{type(exc).__name__}:{exc}",
        )


def write_git_safe_push_report(report: GitSafePushReport, output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
