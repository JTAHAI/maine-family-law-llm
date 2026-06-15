from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app.wizard_new_case import coerce_source_roots, default_case_build_root
from maine_family_law_llm.case_corpus_builder import build_case_corpus


def import_additional_corpus(
    repo_root: Path,
    existing_case_root: Path | None,
    source_roots: Path | Sequence[Path],
    output_root: Path | None = None,
    case_name: str = "",
):
    normalized_sources = coerce_source_roots(source_roots)
    fallback_output_root = Path(existing_case_root).parent if existing_case_root else default_case_build_root()
    resolved_output_root = Path(output_root) if output_root else fallback_output_root
    if case_name.strip():
        resolved_case_name = case_name.strip()
    elif existing_case_root:
        resolved_case_name = f"{Path(existing_case_root).name} expanded"
    elif normalized_sources:
        resolved_case_name = f"{Path(normalized_sources[0]).name.replace('_', ' ').strip()} expanded"
    else:
        resolved_case_name = "Expanded Family Matter"
    return build_case_corpus(
        repo_root=repo_root,
        source_roots=normalized_sources,
        output_root=resolved_output_root,
        case_name=resolved_case_name,
    )
