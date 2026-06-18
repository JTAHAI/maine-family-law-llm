"""Workspace and long-lived corpus intake helpers for case builds."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


WORKSPACE_FOLDER_NAME = "MaineFamilyLawLLM"
CASE_BUILDS_FOLDER_NAME = "CaseBuilds"
WORKSPACE_STATE_FILENAME = "workspace_state.json"
CASE_SOURCE_ROOTS_FILENAME = "case_source_roots.json"
CASE_INGEST_HISTORY_FILENAME = "case_ingest_history.json"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_documents_root() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"


def default_workspace_root() -> Path:
    return default_documents_root() / WORKSPACE_FOLDER_NAME


def default_case_build_root() -> Path:
    return default_workspace_root() / CASE_BUILDS_FOLDER_NAME


def workspace_state_path() -> Path:
    return default_workspace_root() / WORKSPACE_STATE_FILENAME


def case_source_roots_path(case_root: Path) -> Path:
    return case_root / "18_SETTINGS" / CASE_SOURCE_ROOTS_FILENAME


def case_ingest_history_path(case_root: Path) -> Path:
    return case_root / "18_SETTINGS" / CASE_INGEST_HISTORY_FILENAME


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def dedupe_paths(paths: Iterable[Path | str]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        candidate = Path(raw)
        text = str(candidate).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(candidate)
    return normalized


def write_case_source_roots(
    case_root: Path,
    *,
    case_name: str,
    source_roots: Sequence[Path | str],
    parent_case_root: Path | None = None,
) -> Path:
    roots = dedupe_paths(source_roots)
    payload = {
        "case_name": case_name,
        "case_root": str(case_root),
        "parent_case_root": str(parent_case_root) if parent_case_root else "",
        "updated_at": utc_now(),
        "source_root_count": len(roots),
        "source_roots": [
            {
                "path": str(path),
                "exists_now": path.exists(),
            }
            for path in roots
        ],
    }
    path = case_source_roots_path(case_root)
    _write_json(path, payload)
    return path


def read_case_source_roots(case_root: Path) -> list[Path]:
    payload = _read_json(case_source_roots_path(case_root), {})
    rows = payload.get("source_roots", [])
    if isinstance(rows, list):
        values = [Path(str(row.get("path", "") if isinstance(row, dict) else row)) for row in rows]
        return dedupe_paths(values)
    return []


def read_case_ingest_history(case_root: Path) -> list[dict[str, Any]]:
    rows = _read_json(case_ingest_history_path(case_root), [])
    return rows if isinstance(rows, list) else []


def append_case_ingest_history(
    case_root: Path,
    *,
    mode: str,
    case_name: str,
    source_roots_added: Sequence[Path | str],
    cumulative_source_roots: Sequence[Path | str],
    parent_case_root: Path | None = None,
    notes: str = "",
) -> Path:
    history = read_case_ingest_history(case_root)
    history.append(
        {
            "recorded_at": utc_now(),
            "mode": mode,
            "case_name": case_name,
            "case_root": str(case_root),
            "parent_case_root": str(parent_case_root) if parent_case_root else "",
            "source_roots_added": [str(path) for path in dedupe_paths(source_roots_added)],
            "cumulative_source_roots": [str(path) for path in dedupe_paths(cumulative_source_roots)],
            "notes": notes.strip(),
        }
    )
    path = case_ingest_history_path(case_root)
    _write_json(path, history)
    return path


def inherit_case_ingest_history(
    new_case_root: Path,
    *,
    existing_case_root: Path | None,
    mode: str,
    case_name: str,
    source_roots_added: Sequence[Path | str],
    cumulative_source_roots: Sequence[Path | str],
    notes: str = "",
) -> Path:
    inherited: list[dict[str, Any]] = []
    if existing_case_root:
        inherited = read_case_ingest_history(existing_case_root)
    path = case_ingest_history_path(new_case_root)
    _write_json(path, inherited)
    return append_case_ingest_history(
        new_case_root,
        mode=mode,
        case_name=case_name,
        source_roots_added=source_roots_added,
        cumulative_source_roots=cumulative_source_roots,
        parent_case_root=existing_case_root,
        notes=notes,
    )


def expand_case_source_roots(existing_case_root: Path | None, additional_source_roots: Sequence[Path | str]) -> list[Path]:
    previous = read_case_source_roots(existing_case_root) if existing_case_root else []
    return dedupe_paths([*previous, *additional_source_roots])


def load_case_summary(case_root: Path) -> dict[str, Any]:
    proof_path = case_root / "15_PROOF_VALIDATION" / "CASE_BUILD_PROOF.json"
    proof = _read_json(proof_path, {})
    source_manifest = _read_json(case_source_roots_path(case_root), {})
    history = read_case_ingest_history(case_root)
    source_rows = source_manifest.get("source_roots", [])
    available_source_root_count = 0
    missing_source_root_count = 0
    if isinstance(source_rows, list):
        for row in source_rows:
            if isinstance(row, dict):
                path_text = str(row.get("path", "")).strip()
                exists_now = bool(path_text) and Path(path_text).exists()
                if exists_now:
                    available_source_root_count += 1
                else:
                    missing_source_root_count += 1
    return {
        "case_root": str(case_root),
        "case_name": proof.get("case_name") or source_manifest.get("case_name") or case_root.name,
        "total_files_indexed": proof.get("total_files_indexed", 0),
        "legal_matter_items": proof.get("legal_matter_items", 0),
        "source_files_hashed": proof.get("source_files_hashed", 0),
        "total_pdf_pages": proof.get("total_pdf_pages", 0),
        "result": proof.get("result", "UNKNOWN"),
        "source_root_count": source_manifest.get("source_root_count", 0),
        "available_source_root_count": available_source_root_count,
        "missing_source_root_count": missing_source_root_count,
        "history_count": len(history),
        "last_import_at": history[-1]["recorded_at"] if history else source_manifest.get("updated_at", ""),
    }
