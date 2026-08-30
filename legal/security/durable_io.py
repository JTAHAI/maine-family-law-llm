"""Durable, race-resistant local file primitives.

These helpers are intentionally small and dependency-free.  They provide the
bounded regular-file reads and append-only write semantics used by security,
pilot, and release evidence stores.
"""

from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import shutil
import stat
import time
from typing import Callable, Iterator


class DurableIOError(OSError):
    """Raised when a local file operation cannot be completed safely."""


# ``msvcrt.LK_LOCK`` asks the CRT to retry internally.  Under a short burst of
# unrelated writer processes it can nevertheless return ``EDEADLK`` rather
# than wait for the owner to release the one-byte sidecar lock.  Use the
# non-blocking primitive below with an explicit, bounded retry budget instead.
# That preserves cross-process serialization while making a real lock timeout
# an honest failure instead of hanging a desktop workflow indefinitely.
_WINDOWS_LOCK_TIMEOUT_SECONDS = 30.0
_WINDOWS_LOCK_INITIAL_RETRY_SECONDS = 0.01
_WINDOWS_LOCK_MAX_RETRY_SECONDS = 0.10


def required_write_reserve_bytes() -> int:
    """Return the minimum free-space reserve retained after a local write.

    The conservative default prevents a temporary-file atomic replacement from
    consuming the last free blocks. A deployment may raise the reserve; a
    negative/invalid override never disables the guard.
    """

    raw = str(os.environ.get("MFL_MINIMUM_WRITE_RESERVE_BYTES") or "").strip()
    try:
        configured = int(raw) if raw else 64 * 1024 * 1024
    except ValueError:
        configured = 64 * 1024 * 1024
    return max(8 * 1024 * 1024, min(configured, 8 * 1024 * 1024 * 1024))


def ensure_write_capacity(path: str | Path, incoming_bytes: int, *, reserve_bytes: int | None = None) -> None:
    """Fail closed before a local durable write exhausts available storage."""

    target = Path(path)
    required = max(0, int(incoming_bytes)) + (required_write_reserve_bytes() if reserve_bytes is None else max(0, int(reserve_bytes)))
    try:
        free = int(shutil.disk_usage(target.parent).free)
    except OSError as exc:
        raise DurableIOError("storage_capacity_unavailable") from exc
    if free < required:
        raise DurableIOError("storage_reserve_required")


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
            deadline = time.monotonic() + _WINDOWS_LOCK_TIMEOUT_SECONDS
            retry_seconds = _WINDOWS_LOCK_INITIAL_RETRY_SECONDS
            retry_errnos = {
                errno.EACCES,
                errno.EAGAIN,
                getattr(errno, "EDEADLK", 35),
                # Python on current Windows has reported this as Errno 36.
                36,
            }
            while True:
                try:
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in retry_errnos:
                        raise DurableIOError("lock_acquire_failed") from exc
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DurableIOError("lock_timeout") from exc
                    time.sleep(min(retry_seconds, remaining))
                    retry_seconds = min(_WINDOWS_LOCK_MAX_RETRY_SECONDS, retry_seconds * 2)
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
    ensure_write_capacity(file_path, len(raw))
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


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
    *,
    mode: int = 0o600,
    fault_injector: Callable[[str], None] | None = None,
) -> Path:
    """Atomically replace a private file and sync both file and parent dir."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.parent.is_symlink():
        raise DurableIOError("parent_symlink_refused")
    if file_path.exists() and file_path.is_symlink():
        raise DurableIOError("file_symlink_refused")
    ensure_write_capacity(file_path, len(data))
    suffix = f".{os.getpid()}.{os.urandom(8).hex()}.tmp"
    temp_path = file_path.with_name(f".{file_path.name}{suffix}")
    flags = _open_flags(write=True, create=True)
    flags |= os.O_EXCL
    descriptor: int | None = None
    try:
        if fault_injector is not None:
            fault_injector("before_open")
        descriptor = os.open(str(temp_path), flags, mode)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise DurableIOError("atomic_write_failed")
            view = view[written:]
        if fault_injector is not None:
            fault_injector("after_write")
        os.fsync(descriptor)
        if fault_injector is not None:
            fault_injector("after_file_sync_before_replace")
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, mode)
            except OSError:
                pass
        os.close(descriptor)
        descriptor = None
        os.replace(temp_path, file_path)
        if fault_injector is not None:
            fault_injector("after_replace_before_directory_sync")
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
    "ensure_write_capacity",
    "required_write_reserve_bytes",
    "read_bounded_regular_file",
]
