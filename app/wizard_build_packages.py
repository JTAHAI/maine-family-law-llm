from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.case_corpus_builder import create_sample_case_build


def build_role_packages_wizard(repo_root: Path, _case_root: Path | None = None):
    return create_sample_case_build(repo_root)
