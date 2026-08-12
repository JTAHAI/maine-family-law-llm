#!/usr/bin/env python3
"""Create a deterministic, data-only workflow-skill archive.

The packaging convention is adapted from the MIT-licensed package-skill.sh in
zeweihan/A-market-ecm-lawyer-plugin. This implementation rejects symlinks,
absolute/path-traversal entries, executable files, oversized input, and common
cache or credential files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for candidate in (REPO_ROOT, REPO_ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from legal.workflow_skills import SkillManifest, SkillValidationError

_MAX_FILES = 500
_MAX_TOTAL_BYTES = 50 * 1024 * 1024
_EXCLUDED_NAMES = {".DS_Store", ".env", "credentials.json", "secrets.json"}
_EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
_ALLOWED_SUFFIXES = {".json", ".md", ".txt", ".csv"}


class SkillPackageError(ValueError):
    pass


def package_skill(skill_dir: Path, output: Path) -> dict[str, object]:
    root = skill_dir.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise SkillPackageError("skill path is not a directory")
    manifests = list(root.glob("*.json"))
    if len(manifests) != 1:
        raise SkillPackageError("skill directory must contain exactly one top-level JSON manifest")
    manifest_path = manifests[0]
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 256 * 1024:
        raise SkillPackageError("manifest is a symlink or exceeds the size limit")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SkillPackageError("manifest must be a JSON object")
        manifest = SkillManifest.from_dict(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SkillValidationError) as exc:
        raise SkillPackageError(f"invalid workflow manifest: {exc}") from exc
    if root.name != manifest.name:
        raise SkillPackageError(
            f"skill directory name must match manifest name: {root.name!r} != {manifest.name!r}"
        )
    if not manifest.review_required:
        raise SkillPackageError("legal workflow skill packages must remain review-required")
    files: list[Path] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SkillPackageError(f"symlink blocked: {path.relative_to(root)}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.name in _EXCLUDED_NAMES or any(part in _EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise SkillPackageError(f"unsupported skill file type: {relative}")
        mode = path.stat().st_mode
        if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise SkillPackageError(f"executable file blocked: {relative}")
        total += path.stat().st_size
        if total > _MAX_TOTAL_BYTES:
            raise SkillPackageError("skill package exceeds total size limit")
        files.append(path)
    if len(files) > _MAX_FILES:
        raise SkillPackageError("skill package contains too many files")

    destination = output.expanduser().resolve()
    if destination == root or root in destination.parents:
        raise SkillPackageError("output archive must be outside the source skill directory")
    if destination.exists() and destination.is_symlink():
        raise SkillPackageError("symlink output archives are not allowed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix != ".skill":
        destination = destination.with_suffix(".skill")
    timestamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = Path(manifest.name) / path.relative_to(root)
            info = zipfile.ZipInfo(relative.as_posix(), timestamp)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {
        "status": "pass",
        "output": str(destination),
        "file_count": len(files),
        "source_bytes": total,
        "archive_bytes": destination.stat().st_size,
        "sha256": digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = package_skill(args.skill_dir, args.output)
    except (SkillPackageError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
