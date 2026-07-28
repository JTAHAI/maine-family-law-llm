from __future__ import annotations

import hashlib
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

READABLE_EXTENSIONS = frozenset(
    {
        ".csv",
        ".doc",
        ".docx",
        ".eml",
        ".gif",
        ".heic",
        ".jpeg",
        ".jpg",
        ".json",
        ".jsonl",
        ".mbox",
        ".md",
        ".msg",
        ".pdf",
        ".png",
        ".rtf",
        ".tif",
        ".tiff",
        ".txt",
        ".xls",
        ".xlsx",
        ".yaml",
        ".yml",
        ".zip",
    }
)
DEFAULT_LARGE_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_HASH_LIMIT_BYTES = 512 * 1024 * 1024


class InventoryError(ValueError):
    pass


@dataclass(frozen=True)
class InventoryEntry:
    relative_path: str
    extension: str
    size_bytes: int
    modified_ns: int
    is_large: bool
    supported: bool
    sha256: str | None = None
    hash_status: str = "not_requested"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlockedEntry:
    relative_path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MatterInventory:
    root: str
    recursive: bool
    files: tuple[InventoryEntry, ...]
    blocked: tuple[BlockedEntry, ...]
    by_extension: dict[str, int]
    total_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "matter_inventory_v1",
            "root": self.root,
            "recursive": self.recursive,
            "total": len(self.files),
            "total_bytes": self.total_bytes,
            "by_extension": dict(self.by_extension),
            "blocked": [item.to_dict() for item in self.blocked],
            "files": [item.to_dict() for item in self.files],
        }


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_text(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_paths(root: Path, recursive: bool) -> Iterable[Path]:
    if not recursive:
        yield from sorted(root.iterdir(), key=lambda item: item.name.casefold())
        return
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_dirs: list[str] = []
        for name in sorted(dirs, key=str.casefold):
            candidate = current_path / name
            if candidate.is_symlink():
                continue
            safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in sorted(files, key=str.casefold):
            yield current_path / name


def scan_matter_folder(
    folder: Path,
    *,
    recursive: bool = True,
    include_unsupported: bool = False,
    hash_files: bool = False,
    large_file_bytes: int = DEFAULT_LARGE_FILE_BYTES,
    hash_limit_bytes: int = DEFAULT_HASH_LIMIT_BYTES,
) -> MatterInventory:
    """Create a read-only inventory without following symlinks or mutating source files."""

    root = folder.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise InventoryError(f"not a directory: {root}")
    if large_file_bytes < 0 or hash_limit_bytes < 0:
        raise InventoryError("size limits must be non-negative")

    files: list[InventoryEntry] = []
    blocked: list[BlockedEntry] = []
    for path in _iter_paths(root, recursive):
        relative = _relative_text(root, path)
        try:
            if path.is_symlink():
                blocked.append(BlockedEntry(relative, "symlink_not_followed"))
                continue
            if not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            if root not in resolved.parents:
                blocked.append(BlockedEntry(relative, "path_escaped_root"))
                continue
            stat = resolved.stat()
        except OSError as exc:
            blocked.append(BlockedEntry(relative, f"stat_failed:{type(exc).__name__}"))
            continue

        extension = resolved.suffix.lower()
        supported = extension in READABLE_EXTENSIONS
        if not supported and not include_unsupported:
            continue

        sha256: str | None = None
        hash_status = "not_requested"
        if hash_files:
            if stat.st_size > hash_limit_bytes:
                hash_status = "skipped_size_limit"
            else:
                try:
                    sha256 = _sha256_file(resolved)
                    hash_status = "computed"
                except OSError as exc:
                    hash_status = f"failed:{type(exc).__name__}"

        files.append(
            InventoryEntry(
                relative_path=relative,
                extension=extension or "[none]",
                size_bytes=stat.st_size,
                modified_ns=stat.st_mtime_ns,
                is_large=stat.st_size > large_file_bytes,
                supported=supported,
                sha256=sha256,
                hash_status=hash_status,
            )
        )

    files.sort(key=lambda item: (item.extension, item.relative_path.casefold()))
    blocked.sort(key=lambda item: item.relative_path.casefold())
    counter = Counter(item.extension for item in files)
    return MatterInventory(
        root=str(root),
        recursive=recursive,
        files=tuple(files),
        blocked=tuple(blocked),
        by_extension=dict(sorted(counter.items())),
        total_bytes=sum(item.size_bytes for item in files),
    )
