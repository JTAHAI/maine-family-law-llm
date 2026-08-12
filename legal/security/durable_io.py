"""Durable, race-resistant local file primitives.

These helpers are intentionally small and dependency-free.  They provide the
bounded regular-file reads and append-only write semantics used by security,
pilot, and release evidence stores.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat
from typing import Iterator


class DurableIOError(OSError):
    """Raised when a local file operation cannot be completed safely."""


def _open_flags(*, write: bool = False, append: bool = False, create: bool = False) -> int:
    flags = os.O_CLOEXEC if hasattr(os, "O_CLOEXEC") else 0
    # Windows CRT text mode translates newlines and treats Ctrl-Z as EOF.
    # Security blobs, hashes, archives, and UTF-8 bytes must be exact.
    flags |= os.O_BINARY if hasattr(os, "O_BINARY") else 0
    flags |= os.O_WRONLY if write else os.O_RDONLY
    if append:
        flags |= os.O_APPEND
    if create:
        flags |= os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _same_file_identity(path_stat: os.stat_result, fd_stat: os.stat_result) -> bool:
    """Compare path and descriptor identity where the platform exposes it."""

    path_dev = getattr(path_stat, "st_dev", None)
    path_ino = getattr(path_stat, "st_ino", None)
    fd_dev = getattr(fd_stat, "st_dev", None)
    fd_ino = getattr(fd_stat, "st_ino", None)
    if not path_ino or not fd_ino:
        return True
    return path_dev == fd_dev and path_ino == fd_ino


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Windows and some filesystems do not support directory fsync.
        pass
    finally:
        os.close(descriptor)


def read_bounded_regular_file(path: str | Path, *, max_bytes: int) -> bytes:
    """Read a non-symlink regular file without an unbounded allocation.

    The file is opened by descriptor, validated with ``fstat``, and read only up
    to ``max_bytes + 1``.  On platforms with ``O_NOFOLLOW`` the final symlink is
    refused atomically.  Elsewhere, lstat/fstat identity checks close the common
    check/open race.
    """

    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    file_path = Path(path)
    try:
        path_stat = file_path.lstat()
    except OSError as exc:
        raise DurableIOError("file_unavailable") from exc
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise DurableIOError("regular_file_required")
    if path_stat.st_size > max_bytes:
        raise DurableIOError("maximum_bytes_exceeded")

    try:
        descriptor = os.open(str(file_path), _open_flags())
    except OSError as exc:
        raise DurableIOError("file_open_failed") from exc
    try:
        fd_stat = os.fstat(descriptor)
        if not stat.S_ISREG(fd_stat.st_mode):
            raise DurableIOError("regular_file_required")
        if not _same_file_identity(path_stat, fd_stat):
            raise DurableIOError("file_identity_changed")
        if fd_stat.st_size > max_bytes:
            raise DurableIOError("maximum_bytes_exceeded")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise DurableIOError("maximum_bytes_exceeded")
        return raw
    finally:
        os.close(descriptor)


@contextmanager
def exclusive_file_lock(path: str | Path) -> Iterator[None]:
    """Hold a cross-process exclusive lock on a private sidecar file."""

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists() and lock_path.is_symlink():
        raise DurableIOError("lock_symlink_refused")
    flags = _open_flags(write=True, create=True)
    flags |= os.O_RDWR
    flags &= ~os.O_WRONLY
    try:
        descriptor = os.open(str(lock_path), flags, 0o600)
    except OSError as exc:
        raise DurableIOError("lock_open_failed") from exc
    try:
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, 0o600)
            except OSError:
                pass
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def durable_append_text(path: str | Path, text: str) -> None:
    """Append UTF-8 text, flush the file, and durably sync its directory."""

    if not isinstance(text, str) or not text:
        raise DurableIOError("append_text_required")
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.parent.is_symlink():
        raise DurableIOError("parent_symlink_refused")
    if file_path.exists() and file_path.is_symlink():
        raise DurableIOError("file_symlink_refused")

    raw = text.encode("utf-8")
    flags = _open_flags(write=True, append=True, create=True)
    try:
        descriptor = os.open(str(file_path), flags, 0o600)
    except OSError as exc:
        raise DurableIOError("append_open_failed") from exc
    try:
        fd_stat = os.fstat(descriptor)
        if not stat.S_ISREG(fd_stat.st_mode):
            raise DurableIOError("regular_file_required")
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, 0o600)
            except OSError:
                pass
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise DurableIOError("append_write_failed")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(file_path.parent)


def atomic_write_bytes(path: str | Path, data: bytes, *, mode: int = 0o600) -> Path:
    """Atomically replace a private file and sync both file and parent dir."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.parent.is_symlink():
        raise DurableIOError("parent_symlink_refused")
    if file_path.exists() and file_path.is_symlink():
        raise DurableIOError("file_symlink_refused")
    suffix = f".{os.getpid()}.{os.urandom(8).hex()}.tmp"
    temp_path = file_path.with_name(f".{file_path.name}{suffix}")
    flags = _open_flags(write=True, create=True)
    flags |= os.O_EXCL
    descriptor: int | None = None
    try:
        descriptor = os.open(str(temp_path), flags, mode)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise DurableIOError("atomic_write_failed")
            view = view[written:]
        os.fsync(descriptor)
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, mode)
            except OSError:
                pass
        os.close(descriptor)
        descriptor = None
        os.replace(temp_path, file_path)
        _fsync_directory(file_path.parent)
        return file_path
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


__all__ = [
    "DurableIOError",
    "atomic_write_bytes",
    "durable_append_text",
    "exclusive_file_lock",
    "read_bounded_regular_file",
]
