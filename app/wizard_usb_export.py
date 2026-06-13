from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.case_corpus_builder import export_to_usb


def export_case_to_usb(case_root: Path, export_root: Path):
    return export_to_usb(case_root, export_root)
