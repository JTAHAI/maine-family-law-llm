#!/usr/bin/env python3
"""Local hygiene doctor for the open-source Maine Family Law LLM repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_DIR_NAMES = {
    ".local_tmp",
    ".mfl_work",
    ".proofs",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".sentinel_tmp",
    "__pycache__",
    ".eggs",
    "ME_FM_LLM_data",
    "node_modules",
    "dist",
    "build",
    "vector_store",
    "vector_stores",
    "chroma",
    "qdrant",
    "models",
    "weights",
}

FORBIDDEN_FILE_NAMES = {
    ".coverage",
    ".local_server.pid",
}

ROOT_GENERATED_JSON_PREFIXES = (
    "smoke_evidence",
)

ROOT_GENERATED_JSON_NAMES = {
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

FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pdf",
    ".gguf",
    ".safetensors",
}

VENV_DIR_NAMES = {"venv", ".venv", "ME_FM_LLM_venv", "env"}

TESTS_ALLOWED_TOP_LEVEL_FILES = {"conftest.py", "__init__.py"}
TESTS_ALLOWED_TOP_LEVEL_PREFIXES = ("test_",)

REQUIRED_PUBLIC_REPO_FILES = {
    ".gitignore",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/ci.yml",
}

TESTS_FORBIDDEN_TOP_LEVEL_NAMES = {
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


def _is_under_ignored_path(rel: Path) -> bool:
    return any(part == ".git" for part in rel.parts)


def _scan_tests_contamination(repo_root: Path) -> list[str]:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return []
    contaminated: list[str] = []
    for item in tests_dir.iterdir():
        rel = item.relative_to(repo_root).as_posix()
        if item.name in {"__pycache__", ".pytest_cache"}:
            continue
        if item.name in TESTS_FORBIDDEN_TOP_LEVEL_NAMES:
            contaminated.append(rel)
            continue
        if item.is_dir():
            contaminated.append(rel)
            continue
        if item.name in TESTS_ALLOWED_TOP_LEVEL_FILES:
            continue
        if item.name.startswith(TESTS_ALLOWED_TOP_LEVEL_PREFIXES) and item.suffix == ".py":
            continue
        contaminated.append(rel)
    nested_tests = tests_dir / "tests"
    if nested_tests.exists():
        contaminated.append("tests/tests")
    return contaminated


def scan(repo_root: Path, *, allow_venv: bool = False) -> dict[str, object]:
    repo_root = repo_root.resolve()
    forbidden: list[str] = []
    for path in repo_root.rglob("*"):
        rel = path.relative_to(repo_root)
        if _is_under_ignored_path(rel):
            continue
        if allow_venv and any(part in VENV_DIR_NAMES for part in rel.parts):
            continue
        if path.is_dir() and path.name in VENV_DIR_NAMES and not allow_venv:
            forbidden.append(rel.as_posix())
            continue
        if path.is_dir() and (path.name in FORBIDDEN_DIR_NAMES or path.name.endswith(".egg-info")):
            forbidden.append(rel.as_posix())
            continue
        if path.is_file() and path.name in FORBIDDEN_FILE_NAMES:
            forbidden.append(rel.as_posix())
            continue
        if (
            path.is_file()
            and len(rel.parts) == 1
            and path.suffix.lower() == ".json"
            and (
                path.name in ROOT_GENERATED_JSON_NAMES
                or path.name.startswith(ROOT_GENERATED_JSON_PREFIXES)
            )
        ):
            forbidden.append(rel.as_posix())
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            forbidden.append(rel.as_posix())
            continue
        if path.is_file() and path.suffix.lower() == ".txt" and rel.as_posix() not in {"PASS_CHANGES.txt", "requirements.txt", "requirements-dev.txt"}:
            forbidden.append(rel.as_posix())

    missing_required = sorted(
        rel_path for rel_path in REQUIRED_PUBLIC_REPO_FILES if not (repo_root / rel_path).is_file()
    )
    forbidden.extend(f"missing_required_public_repo_file:{item}" for item in missing_required)
    forbidden.extend(_scan_tests_contamination(repo_root))
    forbidden = sorted(set(forbidden))
    status = "pass" if not forbidden else "fail"
    return {
        "schema": "maine_family_law_llm.local_doctor.v2",
        "status": status,
        "safe_to_push": status == "pass",
        "failure_class": "none" if not forbidden else "repo_contamination_detected",
        "strict_by_default": True,
        "venv_allowed": allow_venv,
        "forbidden_paths": forbidden,
        "required_public_repo_files": sorted(REQUIRED_PUBLIC_REPO_FILES),
        "recovery_hint": (
            "Run REPAIR_LOCAL_REPO.ps1 -IncludeVenv or python scripts/clean-local-artifacts.py "
            "--repo-root <repo> --include-venv, then re-run the doctor."
            if forbidden
            else ""
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-venv", action="store_true", help="Permit repo-local venvs for temporary local-only checks.")
    parser.add_argument(
        "--strict-venv",
        action="store_true",
        help="Deprecated compatibility flag; strict venv scanning is now the default.",
    )
    args = parser.parse_args()
    report = scan(Path(args.repo_root), allow_venv=args.allow_venv)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
