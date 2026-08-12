from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path


INVALID_WINDOWS_CHARS = set('<>:"|?*')
RESERVED_DOS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_regular_file(path: Path) -> bool:
    try:
        file_stat = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return stat.S_ISREG(file_stat.st_mode)


def _is_reparse_or_symlink(path: Path) -> bool:
    return path.is_symlink()


def _should_skip_source_path(relative_path: Path) -> bool:
    # python-docx loads its runtime default template from templates/default.docx;
    # the exploded default-docx-template tree is redundant and trips MakeAppx.
    return "docx/templates/default-docx-template/" in relative_path.as_posix()


def _validate_component(component: str) -> list[str]:
    issues: list[str] = []
    if component in {"", ".", ".."}:
        issues.append("dot_or_empty_segment")
        return issues
    if any(ch in INVALID_WINDOWS_CHARS for ch in component):
        issues.append("invalid_windows_character")
    if component.endswith(" "):
        issues.append("trailing_space")
    if component.endswith("."):
        issues.append("trailing_period")
    stem = component.split(".", 1)[0].rstrip(" .").upper()
    if stem in RESERVED_DOS_NAMES:
        issues.append("reserved_dos_device_name")
    if ":" in component:
        issues.append("alternate_data_stream_syntax")
    return issues


@dataclass(frozen=True)
class StagedFile:
    source_root: str
    source_path: str
    package_relative_path: str
    destination_path: str
    size: int
    source_sha256: str
    destination_sha256: str


def _copy_tree(source_root: Path, destination_root: Path, *, destination_prefix: str = "") -> list[StagedFile]:
    source_root = source_root.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    staged: list[StagedFile] = []
    seen_destinations: dict[str, str] = {}
    seen_nfcs: dict[str, str] = {}

    for source_path in sorted(p for p in source_root.rglob("*") if p.is_file()):
        if _is_reparse_or_symlink(source_path) or not _is_regular_file(source_path):
            raise RuntimeError(f"Unsupported non-regular file in source tree: {source_path}")
        try:
            relative_path = source_path.relative_to(source_root)
        except ValueError as exc:
            raise RuntimeError(f"Source path escaped the source root: {source_path}") from exc
        if _should_skip_source_path(relative_path):
            continue
        package_relative = Path(destination_prefix) / relative_path
        package_relative_text = package_relative.as_posix()
        if package_relative.is_absolute():
            raise RuntimeError(f"Absolute package destination rejected: {package_relative_text}")
        source_components = list(relative_path.parts)
        destination_components = list(package_relative.parts)
        for component in source_components + destination_components:
            issues = _validate_component(component)
            if issues:
                raise RuntimeError(f"Unsafe path component '{component}' in {source_path}")
        if any(part == ".." for part in package_relative.parts):
            raise RuntimeError(f"Dot-dot segment rejected: {package_relative_text}")
        destination_path = destination_root / package_relative
        destination_key = package_relative_text.casefold()
        normalized_key = unicodedata.normalize("NFC", package_relative_text).casefold()
        if destination_key in seen_destinations:
            raise RuntimeError(f"Duplicate package destination: {package_relative_text}")
        if normalized_key in seen_nfcs:
            raise RuntimeError(f"Unicode normalization collision: {package_relative_text}")
        seen_destinations[destination_key] = str(source_path)
        seen_nfcs[normalized_key] = str(source_path)
        if not source_path.exists():
            raise RuntimeError(f"Source file disappeared before copy: {source_path}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_sha256 = sha256_file(source_path)
        shutil.copy2(source_path, destination_path)
        if not destination_path.is_file():
            raise RuntimeError(f"Destination file missing after copy: {destination_path}")
        destination_sha256 = sha256_file(destination_path)
        if source_sha256 != destination_sha256:
            raise RuntimeError(f"SHA-256 mismatch after copy: {source_path} -> {destination_path}")
        staged.append(
            StagedFile(
                source_root=str(source_root),
                source_path=str(source_path),
                package_relative_path=package_relative_text,
                destination_path=str(destination_path),
                size=destination_path.stat().st_size,
                source_sha256=source_sha256,
                destination_sha256=destination_sha256,
            )
        )
    return staged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args()

    runtime_root = Path(args.runtime_root)
    assets_root = Path(args.assets_root)
    stage_root = Path(args.stage_root)
    package_root = stage_root / "package"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    package_root.mkdir(parents=True, exist_ok=True)

    staged_files: list[StagedFile] = []
    staged_files.extend(_copy_tree(runtime_root, package_root))
    staged_files.extend(_copy_tree(assets_root, package_root, destination_prefix="Assets"))

    payload = {
        "schema_version": "msix_staging_manifest_v1",
        "runtime_root": str(runtime_root),
        "assets_root": str(assets_root),
        "stage_root": str(stage_root),
        "package_root": str(package_root),
        "file_count": len(staged_files),
        "files": [staged_file.__dict__ for staged_file in staged_files],
    }

    manifest_path = Path(args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
