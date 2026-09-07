"""Remove only test/cache residue from a newly built frozen runtime.

PyInstaller hooks may contribute dependency test fixtures after the spec's
data-file filtering has run.  Those files cannot be part of a Store payload.
This tool is intentionally narrow: it operates only below an explicit runtime
root, refuses links/reparse points, records every candidate, and never removes
production modules, models, documents, user data, or anything outside that
fresh build tree.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def is_link_or_reparse(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(os.lstat(path).st_file_attributes & 0x400)
    except (AttributeError, OSError):
        return path.is_symlink()


def is_residue(relative: Path) -> bool:
    parts = relative.parts
    name = relative.name.lower()
    return (
        "__pycache__" in parts
        or "tests" in parts
        or name.endswith(".pyc")
        or name.endswith(".pyo")
        or ".pyc." in name
    )


def candidates(runtime_root: Path) -> list[Path]:
    root = runtime_root.resolve(strict=True)
    if root.name.lower() != "runtime":
        raise ValueError("runtime_root_must_name_the_fresh_runtime_directory")
    rows: list[Path] = []
    for path in root.rglob("*"):
        if is_link_or_reparse(path):
            raise ValueError("runtime_tree_must_not_contain_links_or_reparse_points")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("runtime_candidate_escaped_root")
        if is_residue(path.relative_to(root)):
            rows.append(path)
    return sorted(rows, key=lambda item: item.as_posix())


def prune(runtime_root: Path, *, apply: bool) -> dict[str, object]:
    root = runtime_root.resolve(strict=True)
    rows = candidates(root)
    removed: list[dict[str, object]] = []
    for path in rows:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if apply:
            path.unlink()
        removed.append({"path": relative, "size": size})
    if apply:
        for directory in sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            if is_link_or_reparse(directory):
                raise ValueError("runtime_tree_must_not_contain_links_or_reparse_points")
            try:
                directory.rmdir()
            except OSError:
                pass
    return {
        "schema": "mfl.store-runtime-residue-prune.v1",
        "status": "applied" if apply else "planned",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "runtime_root_name": root.name,
        "candidate_count": len(rows),
        "candidate_bytes": sum(int(row["size"]) for row in removed),
        "removed": removed,
        "scope": "dependency_test_and_bytecode_residue_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    receipt = prune(args.runtime_root, apply=args.apply)
    write_json_atomic(args.receipt, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
