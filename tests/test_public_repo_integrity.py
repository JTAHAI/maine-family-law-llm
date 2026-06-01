from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_tests_directory_contains_only_tests() -> None:
    allowed_names = {"conftest.py", "__init__.py"}
    forbidden_names = {
        ".dockerignore",
        ".github",
        ".gitignore",
        "ATTRIBUTION.md",
        "CITATION.cff",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "Dockerfile",
        "LICENSE.md",
        "NOTICE.md",
        "README.md",
        "SECURITY.md",
        "SUPPORT.md",
        "configs",
        "docker-compose.yml",
        "docs",
        "eval_data",
        "pyproject.toml",
        "scripts",
    }
    offenders: list[str] = []
    for item in (ROOT / "tests").iterdir():
        if item.name in {"__pycache__", ".pytest_cache"}:
            continue
        if item.name in forbidden_names:
            offenders.append(item.relative_to(ROOT).as_posix())
            continue
        if item.is_dir():
            offenders.append(item.relative_to(ROOT).as_posix())
            continue
        if item.name in allowed_names:
            continue
        if item.name.startswith("test_") and item.suffix == ".py":
            continue
        offenders.append(item.relative_to(ROOT).as_posix())
    assert offenders == []


def test_only_pass_changes_txt_is_packaged() -> None:
    txt_files = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.txt")
        if ".git" not in path.relative_to(ROOT).parts
    )
    assert txt_files == ["PASS_CHANGES.txt"]


def test_strict_doctor_marks_repo_safe_to_push() -> None:
    subprocess.run(
        ["python", "scripts/clean-local-artifacts.py", "--repo-root", str(ROOT), "--include-venv"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    result = subprocess.run(
        ["python", "scripts/doctor-local-repo.py", "--repo-root", str(ROOT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    assert payload["status"] == "pass"
    assert payload["safe_to_push"] is True
    assert payload["forbidden_paths"] == []


def test_no_generated_evidence_json_at_repo_root() -> None:
    offenders = sorted(
        path.name
        for path in ROOT.glob("*.json")
        if path.name.startswith("smoke_evidence")
        or path.name in {
            "enterprise_acceptance_evidence.json",
            "full_ga_workbench_report.json",
            "local_smoke_report.json",
            "local_test_readiness_report.json",
            "networked_source_gate_report.json",
            "operator_handoff_bundle.json",
            "operator_test_battery_evidence.json",
            "post_ga_repo_review_build_path.json",
            "production_promotion_gate_report.json",
            "public_attribution_kit_report.json",
            "reboot_recovery_healthcheck.json",
            "source_release_lock.json",
            "source_sbom.json",
        }
    )
    assert offenders == []
