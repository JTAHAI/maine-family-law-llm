from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.pilot import LaunchEvidenceGate
from legal.release.public_repo_readiness import PublicRepoReadinessAuditor


@dataclass(frozen=True)
class PrePushCheck:
    name: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class PrePushGateReport:
    schema: str
    status: str
    safe_to_push: bool
    production_legal_ready: bool
    project_root: str
    generated_at: str
    checks: tuple[PrePushCheck, ...]
    blockers: tuple[str, ...]
    interpretation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "safe_to_push": self.safe_to_push,
            "production_legal_ready": self.production_legal_ready,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "checks": [check.as_dict() for check in self.checks],
            "blockers": list(self.blockers),
            "interpretation": self.interpretation,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")



def _remove_bytecode_artifacts(project_root: Path) -> None:
    for artifact_name in ("__pycache__", ".pytest_cache", ".ruff_cache", ".mfl_work", ".local_tmp", ".proofs"):
        for path in project_root.rglob(artifact_name):
            if ".git" in path.parts or any(part in {".venv", "venv", "env", "node_modules"} for part in path.parts):
                continue
            shutil.rmtree(path, ignore_errors=True)
    for path in project_root.rglob("*.pyc"):
        if ".git" in path.parts or any(part in {".venv", "venv", "env", "node_modules"} for part in path.parts):
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            pass

def _doctor_check(project_root: Path) -> PrePushCheck:
    result = subprocess.run(
        [sys.executable, "scripts/doctor-local-repo.py", "--repo-root", str(project_root), "--json"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return PrePushCheck(
            name="local_doctor",
            status="fail",
            summary="doctor-local-repo.py did not emit valid JSON",
            details={"returncode": result.returncode, "stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]},
            blockers=("local_doctor_invalid_json",),
        )
    blockers = tuple(str(item) for item in payload.get("forbidden_paths", []))
    status = "pass" if result.returncode == 0 and payload.get("safe_to_push") is True else "fail"
    return PrePushCheck(
        name="local_doctor",
        status=status,
        summary="local source tree hygiene is clean" if status == "pass" else "local source tree hygiene found push blockers",
        details={
            "returncode": result.returncode,
            "safe_to_push": payload.get("safe_to_push"),
            "failure_class": payload.get("failure_class"),
            "forbidden_count": len(blockers),
        },
        blockers=blockers,
    )


def _public_readiness_check(project_root: Path) -> PrePushCheck:
    payload = PublicRepoReadinessAuditor(project_root).audit().as_dict()
    findings = tuple(f"{finding['path']}:{finding['reason']}" for finding in payload.get("findings", []))
    status = "pass" if payload.get("public_source_ready") is True else "fail"
    return PrePushCheck(
        name="public_repo_readiness",
        status=status,
        summary="public source release checks pass" if status == "pass" else "public source release checks found blockers",
        details={
            "checked_files": payload.get("checked_files"),
            "only_one_txt_file": payload.get("only_one_txt_file"),
            "github_ci_present": payload.get("github_ci_present"),
            "release_manifest_clean": payload.get("release_manifest_clean"),
            "production_legal_ready": payload.get("production_legal_ready"),
        },
        blockers=findings,
    )


def _pyproject_version(project_root: Path) -> str:
    text = _read_text(project_root / "pyproject.toml")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.M)
    return match.group(1) if match else ""


def _package_init_version(project_root: Path) -> str:
    text = _read_text(project_root / "src" / "maine_family_law_llm" / "__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _version_consistency_check(project_root: Path) -> PrePushCheck:
    pyproject_version = _pyproject_version(project_root)
    package_version = _package_init_version(project_root)
    release_notes = _read_text(project_root / "docs" / "release-notes.md")
    pass_log = _read_text(project_root / "PASS_CHANGES.txt")
    blockers: list[str] = []
    if not pyproject_version:
        blockers.append("pyproject_version_missing")
    if not package_version:
        blockers.append("package___version___missing")
    if pyproject_version and package_version and pyproject_version != package_version:
        blockers.append(f"version_mismatch:pyproject={pyproject_version}:package={package_version}")
    expected_heading = f"v{pyproject_version}"
    if pyproject_version and expected_heading not in release_notes:
        blockers.append(f"release_notes_missing:{expected_heading}")
    if pyproject_version and expected_heading not in pass_log:
        blockers.append(f"pass_changes_missing:{expected_heading}")
    status = "pass" if not blockers else "fail"
    return PrePushCheck(
        name="version_consistency",
        status=status,
        summary="package metadata, release notes, and pass log agree" if status == "pass" else "release metadata is inconsistent",
        details={"pyproject_version": pyproject_version, "package_version": package_version, "expected_heading": expected_heading},
        blockers=tuple(blockers),
    )


def _launch_gate_fail_closed_check(project_root: Path) -> PrePushCheck:
    report = LaunchEvidenceGate().audit(
        pilot_root=project_root / ".missing_external_launch_evidence" / "pilot",
        release_root=project_root / ".missing_external_launch_evidence" / "release",
    ).as_dict()
    expected_open = [48, 49, 50, 51]
    fail_closed = report.get("status") == "blocked" and report.get("open_passes") == expected_open
    blockers: tuple[str, ...] = () if fail_closed else ("launch_evidence_gate_not_fail_closed_for_missing_external_evidence",)
    return PrePushCheck(
        name="launch_evidence_fail_closed",
        status="pass" if fail_closed else "fail",
        summary=(
            "Pass 48-51 evidence gate remains blocked until external pilot/release evidence is supplied"
            if fail_closed
            else "Pass 48-51 evidence gate did not block missing launch evidence as expected"
        ),
        details={
            "launch_evidence_status": report.get("status"),
            "open_passes": report.get("open_passes"),
            "closed_passes": report.get("closed_passes"),
            "expected_blocked_until_external_evidence": True,
        },
        blockers=blockers,
    )


def _safe_push_wrapper_check(project_root: Path) -> PrePushCheck:
    required_files = (
        "scripts/git-safe-push.py",
        "PUSH_SAFE.ps1",
        "scripts/git-safe-push.ps1",
        "scripts/git-safe-push.sh",
    )
    blockers: list[str] = []
    file_text: dict[str, str] = {}
    for rel in required_files:
        path = project_root / rel
        if not path.is_file():
            blockers.append(f"missing_safe_push_wrapper:{rel}")
            continue
        file_text[rel] = _read_text(path)

    python_text = file_text.get("scripts/git-safe-push.py", "")
    if "run_git_safe_push" not in python_text or "--dry-run" not in python_text:
        blockers.append("python_safe_push_cli_missing_dry_run_or_runner")

    module_text = _read_text(project_root / "legal" / "release" / "git_safe_push.py") if (project_root / "legal" / "release" / "git_safe_push.py").is_file() else ""
    required_module_markers = (
        "git diff",
        "--cached",
        "--quiet",
        "No staged changes; skipping commit.",
        "PRE_PUSH_OUTPUT",
        "test_git_safe_push_v192.py",
    )
    for marker in required_module_markers:
        if marker not in module_text:
            blockers.append(f"git_safe_push_module_missing_marker:{marker}")

    for rel in ("PUSH_SAFE.ps1", "scripts/git-safe-push.ps1", "scripts/git-safe-push.sh"):
        text = file_text.get(rel, "")
        if "scripts" not in text or "git-safe-push.py" not in text:
            blockers.append(f"wrapper_not_delegating_to_python_safe_push:{rel}")
        if "git commit" in text or "git push -u origin" in text:
            blockers.append(f"wrapper_contains_raw_git_commit_or_push:{rel}")

    status = "pass" if not blockers else "fail"
    return PrePushCheck(
        name="git_safe_push_wrapper",
        status=status,
        summary=(
            "safe push wrappers delegate to the no-op-safe Python gate"
            if status == "pass"
            else "safe push wrapper guardrails are missing"
        ),
        details={
            "required_files": list(required_files),
            "no_op_commit_guard": "git diff --cached --quiet",
            "report_output": "docs/external-evidence/git_safe_push_v192.json",
        },
        blockers=tuple(blockers),
    )


def _ci_guardrail_check(project_root: Path) -> PrePushCheck:
    ci_path = project_root / ".github" / "workflows" / "ci.yml"
    if not ci_path.is_file():
        return PrePushCheck(
            name="ci_guardrails",
            status="fail",
            summary="CI workflow is missing",
            blockers=("missing_ci_workflow",),
        )
    text = _read_text(ci_path)
    required_markers = (
        "doctor-local-repo.py",
        "run-chat-library-evidence.py",
        "run-public-source-preflight.py",
        "test_chat_library_v187_input_clear_and_routing.py",
        "test_pass48_51_launch_evidence_gates.py",
        "test_public_source_pre_push_gate_v191.py",
        "test_git_safe_push_v192.py",
    )
    missing = tuple(marker for marker in required_markers if marker not in text)
    return PrePushCheck(
        name="ci_guardrails",
        status="pass" if not missing else "fail",
        summary="CI includes source hygiene, chat/UI, launch-gate, and pre-push checks" if not missing else "CI is missing required guardrail tests",
        details={"required_markers": list(required_markers), "missing_markers": list(missing)},
        blockers=tuple(f"ci_missing_marker:{marker}" for marker in missing),
    )


def run_pre_push_gate(project_root: str | Path = ".") -> PrePushGateReport:
    root = Path(project_root).resolve()
    _remove_bytecode_artifacts(root)
    checks = (
        _doctor_check(root),
        _public_readiness_check(root),
        _version_consistency_check(root),
        _launch_gate_fail_closed_check(root),
        _safe_push_wrapper_check(root),
        _ci_guardrail_check(root),
    )
    blockers = tuple(blocker for check in checks for blocker in check.blockers)
    status = "pass" if not blockers and all(check.status == "pass" for check in checks) else "fail"
    return PrePushGateReport(
        schema="maine_family_law_llm.public_source_pre_push_gate.v2",
        status=status,
        safe_to_push=status == "pass",
        production_legal_ready=False,
        project_root=str(root),
        generated_at=_utc_now(),
        checks=checks,
        blockers=blockers,
        interpretation=(
            "Safe-to-push means the public source tree is clean, push wrappers are no-op safe, and guardrails are present. It does not mean the legal product is GA-shipped; Passes 48-51 still require external attorney sandbox, limited real-matter pilot, release-candidate signoff, and GA shipment signoff evidence."
        ),
    )


def write_pre_push_gate(project_root: str | Path, output_path: str | Path) -> PrePushGateReport:
    report = run_pre_push_gate(project_root)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return report
