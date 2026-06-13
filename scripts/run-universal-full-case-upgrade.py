from __future__ import annotations

import subprocess
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.case_corpus_builder import (
    bootstrap_repository,
    create_sample_case_build,
    write_repo_upgrade_proof,
)


def main() -> int:
    repo_root = REPO_ROOT
    bootstrap_repository(repo_root)
    sample_case = create_sample_case_build(repo_root)
    original_repo_path = Path(r"D:\dev\maine-family-law-llm_git")
    dirty_status = subprocess.run(
        ["git", "-C", str(original_repo_path), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    copied_files_count = sum(1 for path in repo_root.rglob("*") if path.is_file() and ".git" not in path.parts)
    write_repo_upgrade_proof(
        repo_root,
        created_or_forked="forked_safe_copy",
        original_repo_path=str(original_repo_path),
        original_branch=subprocess.run(
            ["git", "-C", str(original_repo_path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        original_commit=subprocess.run(
            ["git", "-C", str(original_repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        original_dirty_status=dirty_status,
        copied_files_count=copied_files_count,
        sample_case=sample_case,
        tests_run=[],
        tests_passed=[],
        tests_failed=[],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
