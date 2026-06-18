from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.case_corpus_builder import build_case_corpus
from maine_family_law_llm.case_workspace import (
    default_case_build_root as workspace_default_case_build_root,
    default_documents_root as workspace_default_documents_root,
    default_workspace_root as workspace_default_workspace_root,
)


def default_documents_root() -> Path:
    return workspace_default_documents_root()


def default_workspace_root() -> Path:
    return workspace_default_workspace_root()


def default_case_build_root() -> Path:
    return workspace_default_case_build_root()


def coerce_source_roots(source_roots: Path | Sequence[Path]) -> list[Path]:
    items = [source_roots] if isinstance(source_roots, Path) else list(source_roots)
    normalized: list[Path] = []
    seen: set[str] = set()
    for item in items:
        candidate = Path(item)
        candidate_text = str(candidate).strip()
        if candidate_text in {"", "."}:
            continue
        key = candidate_text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(candidate)
    return normalized


def suggest_case_name(source_roots: Sequence[Path]) -> str:
    labels = [Path(path).name.replace("_", " ").strip() for path in source_roots if Path(path).name.strip()]
    if not labels:
        return "Imported Family Matter"
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} consolidated case"


def launch_new_case_wizard(
    repo_root: Path,
    source_roots: Path | Sequence[Path],
    output_root: Path | None = None,
    case_name: str = "",
):
    normalized_sources = coerce_source_roots(source_roots)
    resolved_output_root = Path(output_root) if output_root else default_case_build_root()
    resolved_case_name = case_name.strip() or suggest_case_name(normalized_sources)
    return build_case_corpus(
        repo_root=repo_root,
        source_roots=normalized_sources,
        output_root=resolved_output_root,
        case_name=resolved_case_name,
    )
