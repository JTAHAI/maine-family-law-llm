#!/usr/bin/env python3
"""Remove generated local build/test artifacts from the source tree.

The cleaner is intentionally safe for source-controlled code while being strict about
repo-local runtime debris. Corpora, model weights, vector stores, OCR caches, and local
virtual environments belong outside this repository.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

DEFAULT_DIR_NAMES = {
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".mfl_work",
    ".proofs",
    ".sentinel_tmp",
    "__pycache__",
    "build",
    "dist",
    ".eggs",
    "model_store",
    "model_registry",
    "benchmark_runs",
    "runtime_profiles",
    "quarantine",
}

DEFAULT_FILE_NAMES = {
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

VENV_DIR_NAMES = {".venv", "venv", "env", "ME_FM_LLM_venv"}
TESTS_COPIED_REPO_NAMES = {
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


def _remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def _should_remove_from_tests(repo_root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return False
    if len(rel.parts) < 2 or rel.parts[0] != "tests":
        return False
    if len(rel.parts) == 2 and rel.parts[1] in TESTS_COPIED_REPO_NAMES:
        return True
    return len(rel.parts) == 2 and path.is_file() and path.suffix.lower() == ".json"


def clean(repo_root: Path, *, include_venv: bool = False) -> list[str]:
    repo_root = repo_root.resolve()
    removed: list[str] = []

    for path in sorted(repo_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        rel = path.relative_to(repo_root)
        parts = set(rel.parts)
        if ".git" in parts:
            continue
        is_venv_dir = path.name in VENV_DIR_NAMES or path.name.startswith(".venv-")
        if not include_venv and (any(part in VENV_DIR_NAMES for part in parts) or any(part.startswith(".venv-") for part in parts)):
            continue
        should_remove = False
        if path.is_dir() and path.name in DEFAULT_DIR_NAMES:
            should_remove = True
        if path.is_dir() and path.name.endswith(".egg-info"):
            should_remove = True
        if include_venv and path.is_dir() and is_venv_dir:
            should_remove = True
        if path.is_file() and path.name in DEFAULT_FILE_NAMES:
            should_remove = True
        if (
            path.is_file()
            and len(rel.parts) == 1
            and path.suffix.lower() == ".json"
            and (
                path.name in ROOT_GENERATED_JSON_NAMES
                or path.name.startswith(ROOT_GENERATED_JSON_PREFIXES)
            )
        ):
            should_remove = True
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            should_remove = True
        if _should_remove_from_tests(repo_root, path):
            should_remove = True
        if should_remove and _remove_path(path):
            removed.append(rel.as_posix())

    return sorted(set(removed))


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean generated local artifacts from the repo tree.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--include-venv", action="store_true", help="Also remove repo-local .venv/venv/env folders.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable cleanup report.")
    args = parser.parse_args()

    removed = clean(Path(args.repo_root), include_venv=args.include_venv)
    if args.json:
        print(json.dumps({"schema": "maine_family_law_llm.local_clean.v1", "removed": removed}, indent=2))
    else:
        for item in removed:
            print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
