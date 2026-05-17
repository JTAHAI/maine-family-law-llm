#!/usr/bin/env python3
"""Remove generated local build/test artifacts from the source tree.

This is intentionally conservative: it removes Python/package/test metadata that can be
created by editable installs or test runs, but it does not remove legal data roots,
corpora, runtime stores, or virtual environments unless explicitly requested.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DEFAULT_DIR_NAMES = {
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "build",
    "dist",
    ".eggs",
}

VENV_DIR_NAMES = {".venv", "venv", "env"}


def _remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def clean(repo_root: Path, *, include_venv: bool = False) -> list[str]:
    repo_root = repo_root.resolve()
    removed: list[str] = []

    for path in sorted(repo_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        rel = path.relative_to(repo_root)
        parts = set(rel.parts)
        should_remove = False
        if path.is_dir() and path.name in DEFAULT_DIR_NAMES:
            should_remove = True
        if path.is_dir() and path.name.endswith(".egg-info"):
            should_remove = True
        if include_venv and path.is_dir() and path.name in VENV_DIR_NAMES:
            should_remove = True
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            should_remove = True
        if should_remove:
            if any(part in {".git"} for part in parts):
                continue
            if _remove_path(path):
                removed.append(rel.as_posix())

    return sorted(removed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean generated local artifacts from the repo tree.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--include-venv", action="store_true", help="Also remove repo-local .venv/venv/env folders.")
    args = parser.parse_args()

    removed = clean(Path(args.repo_root), include_venv=args.include_venv)
    for item in removed:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
