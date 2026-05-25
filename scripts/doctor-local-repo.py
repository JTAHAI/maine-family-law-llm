#!/usr/bin/env python3
"""Local hygiene doctor for the open-source Maine Family Law LLM repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_DIR_NAMES = {
    ".local_tmp",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
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


VENV_DIR_NAMES = {"venv", ".venv", "ME_FM_LLM_venv"}


def scan(repo_root: Path, *, allow_venv: bool = False) -> dict[str, object]:
    repo_root = repo_root.resolve()
    forbidden: list[str] = []
    for path in repo_root.rglob("*"):
        rel = path.relative_to(repo_root)
        if ".git" in rel.parts or ".proofs" in rel.parts:
            continue
        if allow_venv and any(part in VENV_DIR_NAMES for part in rel.parts):
            continue
        if path.is_dir() and path.name in VENV_DIR_NAMES and not allow_venv:
            forbidden.append(rel.as_posix())
            continue
        if path.is_dir() and (path.name in FORBIDDEN_DIR_NAMES or path.name.endswith(".egg-info")):
            forbidden.append(rel.as_posix())
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            forbidden.append(rel.as_posix())
            continue
        if path.is_file() and path.suffix.lower() == ".txt" and rel.as_posix() != "PASS_CHANGES.txt":
            forbidden.append(rel.as_posix())
    nested_tests = repo_root / "tests" / "tests"
    if nested_tests.exists():
        forbidden.append("tests/tests")
    return {
        "schema": "maine_family_law_llm.local_doctor.v1",
        "status": "pass" if not forbidden else "fail",
        "failure_class": "none" if not forbidden else "repo_contamination_detected",
        "forbidden_paths": sorted(set(forbidden)),
        "recovery_hint": "Run REPAIR_LOCAL_REPO.ps1 and verify no generated artifacts remain." if forbidden else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-venv", action="store_true")
    parser.add_argument("--strict-venv", action="store_true")
    args = parser.parse_args()
    report = scan(Path(args.repo_root), allow_venv=(args.allow_venv or not args.strict_venv))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
