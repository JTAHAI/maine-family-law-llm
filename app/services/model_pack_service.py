"""Explicit offline signed-model import; never a downloader or runtime installer.

Uploads are bounded chunks in an operator-owned external store. A complete pack
is inspected before the separate activation consent. Registries and all loader
bytes must have independently trusted admission. No request accepts a path,
URL, trust key, executable, or worker credential.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import struct
import threading
import time
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from legal.fast_interchange.admission import AdmissionAuthority, canonical, digest
from legal.fast_interchange.snapshot import VerifiedSnapshot
from legal.fast_interchange.worker import HotSwapRegistry, _relative
from legal.security.durable_io import atomic_write_bytes, ensure_write_capacity, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path, strict_json_loads

MAX_PACK_BYTES = 3 * 1024**3
CHUNK_BYTES = 1024**2
METADATA = frozenset({"releases.json", "artifacts.json", "admission.json"})
_ID = re.compile(r"[a-f0-9]{32}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_ACTIVE_STATES = {
    "uploading",
    "resuming",
    "verifying",
    "canceling",
    "ready_to_activate",
    "activating",
}
_EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()


def owner_digest(scope):
    """Explicit local-admin recovery scope, not a cross-session access shortcut."""
    if scope.get("role") != "admin":
        raise ModelPackError("model_pack_local_admin_confirmation_required", 403)
    return digest({name: scope[name] for name in ("tenant_id", "matter_id", "role")})


def chunk_chain(previous, offset, data):
    return hashlib.sha256(
        f"{previous}:{offset}:{len(data)}:{hashlib.sha256(data).hexdigest()}".encode("ascii")
    ).hexdigest()


@contextmanager
def verification_lease(root):
    """Non-blocking OS lease; a second app cannot recover a live verification."""
    path = external_root(root / ".verification.lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    locked = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise ModelPackError("model_pack_verification_busy") from exc
        yield
    finally:
        if locked:
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class ModelPackError(ValueError):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code, self.status_code = code, status_code


def external_root(value: Path, forbidden_roots=()) -> Path:
    original = Path(value).absolute()
    for candidate in (original, *original.parents):
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise ModelPackError("model_pack_store_link_forbidden")
    root = original.resolve()
    if str(original).startswith(("\\\\", "//")):
        raise ModelPackError("model_pack_local_disk_required")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        drive_type = ctypes.WinDLL("kernel32", use_last_error=True).GetDriveTypeW
        drive_type.argtypes, drive_type.restype = [wintypes.LPCWSTR], wintypes.UINT
        if drive_type(root.anchor) == 4:  # DRIVE_REMOTE, including mapped shares.
            raise ModelPackError("model_pack_local_disk_required")
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise ModelPackError("model_pack_external_store_required")
    for forbidden in forbidden_roots:
        excluded = Path(forbidden).resolve()
        if root == excluded or excluded in root.parents or root in excluded.parents:
            raise ModelPackError("model_pack_external_store_required")
    return root


def _bounded_zip(path: Path) -> zipfile.ZipFile:
    # Bound the central directory BEFORE ZipFile allocates entries. ZIP64 and
    # compression are deliberately unsupported by the initial offline format.
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 65557))
        tail = handle.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        raise ModelPackError("model_pack_archive_invalid")
    _, disk, start_disk, on_disk, count, size, start, comment = struct.unpack(
        "<4s4H2IH", tail[offset : offset + 22]
    )
    if (
        disk
        or start_disk
        or on_disk != count
        or not 4 <= count <= 512
        or size > 1024**2
        or start == 0xFFFFFFFF
        or comment
        or offset + 22 != len(tail)
        or start + size + 22 != path.stat().st_size
    ):
        raise ModelPackError("model_pack_archive_bounds_invalid")
    archive = zipfile.ZipFile(path)
    names = set()
    total = 0
    try:
        for item in archive.infolist():
            name = _relative(item.filename, "model_pack_archive_path_invalid")
            mode = item.external_attr >> 16
            if (
                name != item.filename
                or name.casefold() in names
                or item.is_dir()
                or item.flag_bits & 1
                or item.compress_type != zipfile.ZIP_STORED
                or item.compress_size != item.file_size
                or not 1 <= item.file_size <= MAX_PACK_BYTES
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
            ):
                raise ModelPackError("model_pack_archive_entry_forbidden")
            names.add(name.casefold())
            total += item.file_size
        if total > MAX_PACK_BYTES or not METADATA <= set(archive.namelist()):
            raise ModelPackError("model_pack_archive_inventory_invalid")
        return archive
    except Exception:
        archive.close()
        raise


class ModelPackService:
    """One explicit import at a time, protected receipts via caller's audit store.

    Encrypted state is content-free and scope-hashed. A process restart never
    auto-resumes verification or activates a partial pack. Completed versions
    are immutable by identity; activation replaces only an atomic pointer.
    """

    def __init__(self, root: Path, authority: AdmissionAuthority, *, forbidden_roots=()):
        self.root = external_root(root, forbidden_roots)
        self.authority = authority
        self.lock = threading.RLock()
        self.owner = uuid.uuid4().hex
        self.cancel_flags: dict[str, threading.Event] = {}
        self.encryptor = LocalEnvelopeEncryptor("local-development-key-change-me")
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("uploads", "packs", "trash"):
            path = self.root / name
            external_root(path, forbidden_roots)
            path.mkdir(exist_ok=True)

    def _load(self):
        path = self.root / "pack-state.json.enc"
        if not path.exists():
            return {
                "schema": "fi_offline_packs_v1",
                "jobs": {},
                "active": "",
                "previous": "",
                "installed": {},
                "removed": {},
                "transaction": None,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(path, max_bytes=4 * 1024**2, require_object=True)
            )
            if (
                value["schema"] != "fi_offline_packs_v1"
                or not isinstance(value["jobs"], dict)
                or len(value["jobs"]) > 32
            ):
                raise ValueError
            for key in ("active", "previous"):
                if value[key] and not _HASH.fullmatch(value[key]):
                    raise ValueError
            for key in ("installed", "removed"):
                value.setdefault(key, {})
                if not isinstance(value[key], dict) or len(value[key]) > 32:
                    raise ValueError
                if any(not _HASH.fullmatch(item) for item in value[key]):
                    raise ValueError
            value.setdefault("transaction", None)
            transaction = value["transaction"]
            if transaction is not None and (
                not isinstance(transaction, dict)
                or transaction.get("kind") not in {"activate", "remove", "restore"}
                or not _ID.fullmatch(str(transaction.get("id", "")))
                or not _HASH.fullmatch(str(transaction.get("pack_id", "")))
                or not _HASH.fullmatch(str(transaction.get("owner_scope", "")))
            ):
                raise ValueError
            return value
        except Exception as exc:
            raise ModelPackError("model_pack_state_unavailable") from exc

    def _save(self, state):
        atomic_write_bytes(
            self.root / "pack-state.json.enc", canonical(self.encryptor.encrypt_json(state))
        )

    @staticmethod
    def _idle(state):
        if state.get("transaction"):
            raise ModelPackError("model_pack_transaction_recovery_required")

    def _job(self, state, job_id, scope):
        if not _ID.fullmatch(job_id):
            raise ModelPackError("model_pack_job_unavailable", 404)
        row = state["jobs"].get(job_id)
        if not row or row["scope"] != digest(scope):
            raise ModelPackError("model_pack_job_unavailable", 404)
        if row["owner"] != self.owner and row["status"] in {"resuming", "verifying", "canceling"}:
            try:
                with verification_lease(self.root):
                    row["status"] = "interrupted"
                    row["error"] = "model_pack_verification_interrupted_resume_required"
            except ModelPackError as exc:
                if exc.code != "model_pack_verification_busy":
                    raise
        return row

    @staticmethod
    def _public(row):
        keys = (
            "job_id",
            "status",
            "received_bytes",
            "total_bytes",
            "verified_bytes",
            "error",
            "pack_id",
            "summary",
            "prefix_chain",
        )
        return {
            **{key: row.get(key) for key in keys},
            "review_required": True,
            "network_used": False,
        }

    def begin(self, *, scope, total_bytes, audit):
        if type(total_bytes) is not int or not 1 <= total_bytes <= MAX_PACK_BYTES:
            raise ModelPackError("model_pack_size_invalid", 413)
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            if any(row["status"] in _ACTIVE_STATES for row in state["jobs"].values()):
                raise ModelPackError("model_pack_import_busy")
            if len(state["jobs"]) >= 32 or len(list((self.root / "packs").iterdir())) >= 16:
                raise ModelPackError("model_pack_store_capacity")
            ensure_write_capacity(self.root / "uploads" / "reserve", 3 * total_bytes)
            job_id = uuid.uuid4().hex
            row = {
                "job_id": job_id,
                "owner": self.owner,
                "scope": digest(scope),
                "owner_scope": owner_digest(scope),
                "status": "uploading",
                "total_bytes": total_bytes,
                "received_bytes": 0,
                "verified_bytes": 0,
                "error": "",
                "pack_id": "",
                "summary": None,
                "prefix_chain": _EMPTY_CHAIN,
            }
            audit("model_pack_import_started", digest({"job_id": job_id, "bytes": total_bytes}))
            (self.root / "uploads" / job_id).mkdir(mode=0o700)
            state["jobs"][job_id] = row
            self._save(state)
            return self._public(row)

    def chunk(self, job_id, *, scope, offset, data):
        if type(offset) is not int or not 0 < len(data) <= CHUNK_BYTES:
            raise ModelPackError("model_pack_chunk_invalid", 413)
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._job(state, job_id, scope)
            if (
                row["status"] == "uploading"
                and row.get("last_chunk")
                == {
                    "offset": offset,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                and offset + len(data) == row["received_bytes"]
            ):
                # A lost response is retryable; it must not append duplicate bytes.
                return self._public(row)
            if (
                row["status"] != "uploading"
                or offset != row["received_bytes"]
                or offset + len(data) > row["total_bytes"]
            ):
                raise ModelPackError("model_pack_chunk_offset_mismatch")
            path = self.root / "uploads" / job_id / "incoming.zip"
            external_root(path)
            if (path.stat().st_size if path.exists() else 0) != offset:
                raise ModelPackError("model_pack_partial_state_changed_restart_import")
            if len(data) != min(CHUNK_BYTES, row["total_bytes"] - offset):
                raise ModelPackError("model_pack_chunk_layout_invalid")
            ensure_write_capacity(path, len(data))
            with path.open("ab") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            row["received_bytes"] += len(data)
            row["prefix_chain"] = chunk_chain(row.get("prefix_chain", _EMPTY_CHAIN), offset, data)
            row["last_chunk"] = {
                "offset": offset,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            self._save(state)
            return self._public(row)

    def status(self, job_id, *, scope):
        with self.lock:
            return self._public(self._job(self._load(), job_id, scope))

    def resume(self, job_id, *, scope, expected_bytes, prefix_chain, audit):
        """Rebind only after explicit admin consent and a matching file prefix.

        Never guess that a different browser session owns a job. Ordinary
        status/chunk/cancel still require the exact session digest.
        """
        with verification_lease(self.root):
            with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                state = self._load()
                self._idle(state)
                row = state["jobs"].get(job_id) if _ID.fullmatch(job_id) else None
                if not row or row.get("owner_scope") != owner_digest(scope):
                    raise ModelPackError("model_pack_job_unavailable", 404)
                if row["status"] not in {
                    "uploading",
                    "resuming",
                    "verifying",
                    "canceling",
                    "interrupted",
                    "canceled",
                    "failed",
                    "ready_to_activate",
                    "activated",
                }:
                    raise ModelPackError("model_pack_resume_state_invalid")
                if expected_bytes != row["received_bytes"] or prefix_chain != row.get(
                    "prefix_chain"
                ):
                    raise ModelPackError("model_pack_resume_prefix_changed")
                audit(
                    "model_pack_resume_authorized",
                    digest(
                        {"job_id": job_id, "bytes": expected_bytes, "prefix_chain": prefix_chain}
                    ),
                )
                row.update(status="resuming", owner=self.owner, scope=digest(scope), error="")
                self._save(state)
                flag = self.cancel_flags[job_id] = threading.Event()
            try:
                deadline = time.monotonic() + 120
                path = external_root(self.root / "uploads" / job_id / "incoming.zip")
                actual_bytes = path.stat().st_size if path.exists() else 0
                if (
                    not expected_bytes
                    <= actual_bytes
                    <= min(MAX_PACK_BYTES, expected_bytes + CHUNK_BYTES)
                ):
                    raise ModelPackError("model_pack_resume_disk_state_changed")
                chain, offset = _EMPTY_CHAIN, 0
                if expected_bytes:
                    with path.open("rb") as handle:
                        while offset < expected_bytes:
                            if flag.is_set() or self._load()["jobs"][job_id]["status"] in {
                                "canceling",
                                "canceled",
                            }:
                                flag.set()
                                raise ModelPackError("model_pack_canceled")
                            if time.monotonic() > deadline:
                                raise ModelPackError("model_pack_resume_deadline")
                            block = handle.read(min(CHUNK_BYTES, expected_bytes - offset))
                            if not block:
                                raise ModelPackError("model_pack_resume_disk_state_changed")
                            chain = chunk_chain(chain, offset, block)
                            offset += len(block)
                if chain != prefix_chain:
                    raise ModelPackError("model_pack_resume_prefix_changed")
                with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                    state = self._load()
                    row = self._job(state, job_id, scope)
                    if row["status"] != "resuming" or flag.is_set():
                        raise ModelPackError("model_pack_canceled")
                    audit(
                        "model_pack_resume_verified",
                        digest(
                            {
                                "job_id": job_id,
                                "prefix_chain": chain,
                                "discarded_uncommitted_bytes": actual_bytes - expected_bytes,
                            }
                        ),
                    )
                    if actual_bytes > expected_bytes:
                        # Explicit recovery discards ONLY this upload's torn tail.
                        # Committed prefix was rehashed; the user's ZIP is untouched.
                        with path.open("r+b") as handle:
                            handle.truncate(expected_bytes)
                            handle.flush()
                            os.fsync(handle.fileno())
                    row.update(status="uploading", verified_bytes=0, error="")
                    self._save(state)
                    return self._public(row)
            except Exception:
                with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                    state = self._load()
                    row = self._job(state, job_id, scope)
                    row.update(
                        status="canceled"
                        if flag.is_set() or row["status"] in {"canceled", "canceling"}
                        else "failed",
                        error="model_pack_resume_failed",
                    )
                    self._save(state)
                raise
            finally:
                self.cancel_flags.pop(job_id, None)

    def inspect(self, job_id, *, scope, audit):
        with verification_lease(self.root):
            return self._inspect(job_id, scope=scope, audit=audit)

    def _inspect(self, job_id, *, scope, audit):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._job(state, job_id, scope)
            if row["status"] != "uploading" or row["received_bytes"] != row["total_bytes"]:
                raise ModelPackError("model_pack_upload_incomplete")
            audit("model_pack_verification_started", digest({"job_id": job_id}))
            row["status"], row["owner"] = "verifying", self.owner
            self._save(state)
            flag = self.cancel_flags[job_id] = threading.Event()
        deadline = time.monotonic() + 300

        def check():
            current = self._load()["jobs"].get(job_id, {})
            if current.get("status") in {"canceling", "canceled"}:
                flag.set()
            if flag.is_set():
                raise ModelPackError("model_pack_canceled")
            if time.monotonic() > deadline:
                raise ModelPackError("model_pack_verification_deadline")

        workspace = self.root / "uploads" / job_id
        # Each retry owns a fresh directory; an interrupted tree is never reused.
        stage = workspace / ("verified-" + uuid.uuid4().hex)
        try:
            external_root(workspace)
            stage.mkdir(mode=0o700)
            with _bounded_zip(workspace / "incoming.zip") as archive:
                docs = {}
                for name in METADATA:
                    info = archive.getinfo(name)
                    if info.file_size > 2 * 1024**2:
                        raise ModelPackError("model_pack_metadata_too_large")
                    docs[name] = strict_json_loads(
                        archive.read(name), max_bytes=2 * 1024**2, require_object=True
                    )
                inspection_authority = self.authority.inspection_only()
                inspection_authority.verify(
                    docs["admission.json"],
                    releases=docs["releases.json"],
                    artifacts=docs["artifacts.json"],
                )
                registry = replace(
                    HotSwapRegistry.from_dicts(
                        root=stage, releases=docs["releases.json"], artifacts=docs["artifacts.json"]
                    ),
                    admission_authority=inspection_authority,
                    signed_catalog=docs["admission.json"],
                )
                expected = {}
                summaries = []
                for release in registry.releases.values():
                    registry.select(release.model_id, allow_test_only=False)
                    grant = registry.admission(release)
                    binding = registry.bindings[release.release_id]
                    summaries.append(
                        {
                            **release.public(),
                            "licenses": grant.licenses.model_dump(),
                            "evaluation_basis": grant.evaluation.dataset_kind,
                            "compatibility": grant.compatibility.model_dump(),
                        }
                    )
                    for item in (
                        *binding.base_inventory.files,
                        *binding.tokenizer_inventory.files,
                        *binding.adapter_inventory.files,
                        binding.adapter_config,
                    ):
                        if item.path in METADATA or (
                            item.path.casefold() in {key.casefold() for key in expected}
                            and expected.get(item.path) != item
                        ):
                            raise ModelPackError("model_pack_inventory_conflict")
                        expected[item.path] = item
                if set(archive.namelist()) != METADATA | set(expected):
                    raise ModelPackError("model_pack_unlisted_or_missing_file")
                size = sum(item.bytes for item in expected.values())
                if size > MAX_PACK_BYTES:
                    raise ModelPackError("model_pack_expanded_size_invalid")
                ensure_write_capacity(stage / "reserve", size * 2)
                for name, value in docs.items():
                    atomic_write_bytes(stage / name, canonical(value))
                verified = 0
                for name, item in expected.items():
                    check()
                    if archive.getinfo(name).file_size != item.bytes:
                        raise ModelPackError("model_pack_file_size_mismatch")
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    hasher, count = hashlib.sha256(), 0
                    with archive.open(name) as source, target.open("xb") as dest:
                        while block := source.read(CHUNK_BYTES):
                            check()
                            count += len(block)
                            hasher.update(block)
                            dest.write(block)
                        dest.flush()
                        os.fsync(dest.fileno())
                    if count != item.bytes or hasher.hexdigest() != item.sha256:
                        raise ModelPackError("model_pack_file_hash_mismatch")
                    verified += count
                    with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                        progress = self._load()
                        self._job(progress, job_id, scope)["verified_bytes"] = verified
                        self._save(progress)
                snapshot = VerifiedSnapshot()
                try:
                    for release in registry.releases.values():
                        snapshot.prepare(
                            stage,
                            registry.bindings[release.release_id],
                            strict_models=True,
                            maximum_bytes=registry.admission(
                                release
                            ).compatibility.max_resident_bytes,
                            check_cancellation=check,
                        )
                finally:
                    snapshot.close()
                check()
                pack_id = digest(docs["admission.json"])
                with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                    check()
                    state = self._load()
                    row = self._job(state, job_id, scope)
                    if row["status"] != "verifying":
                        raise ModelPackError("model_pack_canceled")
                    audit("model_pack_verified", pack_id)
                    target = self.root / "packs" / pack_id
                    if pack_id in state["removed"]:
                        raise ModelPackError("model_pack_restore_removed_pack_first")
                    if (
                        state["installed"].get(pack_id, {}).get("owner_scope", row["owner_scope"])
                        != row["owner_scope"]
                    ):
                        raise ModelPackError("model_pack_owned_by_another_scope")
                    if target.exists():
                        existing = self.registry(external_root(target), inspection=True)
                        if digest(existing.signed_catalog) != pack_id:
                            raise ModelPackError("model_pack_existing_identity_changed")
                        for release in existing.releases.values():
                            existing.bindings[release.release_id].verify(target)
                    else:
                        os.replace(stage, target)
                    row.update(
                        status="ready_to_activate",
                        pack_id=pack_id,
                        summary={
                            "models": summaries,
                            "installed_bytes": size,
                            "shared_base_copies": 1,
                            "requires_worker_restart": True,
                        },
                    )
                    state["installed"][pack_id] = {
                        "owner_scope": row["owner_scope"],
                        "summary": row["summary"],
                    }
                    self._save(state)
                    return self._public(row)
        except Exception as exc:
            code = getattr(exc, "code", "") or str(exc)
            if not re.fullmatch(r"(?:model_pack|fast_interchange)_[a-z0-9_]+", code):
                code = "model_pack_verification_failed"
            with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
                state = self._load()
                row = self._job(state, job_id, scope)
                row.update(status="canceled" if flag.is_set() else "failed", error=code)
                self._save(state)
                audit("model_pack_verification_failed", digest({"job_id": job_id, "code": code}))
            raise ModelPackError(code) from exc
        finally:
            self.cancel_flags.pop(job_id, None)

    def cancel(self, job_id, *, scope, audit):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._job(state, job_id, scope)
            audit("model_pack_cancel_requested", digest({"job_id": job_id}))
            if row["status"] in {"verifying", "resuming"}:
                if job_id in self.cancel_flags:
                    self.cancel_flags[job_id].set()
                row["status"] = "canceling"
            elif row["status"] in {"uploading", "ready_to_activate", "interrupted"}:
                row["status"] = "canceled"
            self._save(state)
            return self._public(row)

    def activate(self, job_id, *, scope, audit, pack_id):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._job(state, job_id, scope)
            if row["status"] != "ready_to_activate" or row["pack_id"] != pack_id:
                raise ModelPackError("model_pack_activation_consent_changed")
            self._verify_pack(pack_id)
            audit("model_pack_activation_authorized", pack_id)
            self._start_transaction(state, "activate", pack_id, scope, job_id=job_id)
            row["status"] = "activating"
            self._save(state)
            self._finish_transaction(state, scope=scope, audit=audit)
            return self._public(row)

    def _verify_pack(self, pack_id, *, root=None):
        if not _HASH.fullmatch(str(pack_id)):
            raise ModelPackError("model_pack_identity_invalid")
        root = external_root(root or self.root / "packs" / pack_id)
        registry = self.registry(root, inspection=True)
        if digest(registry.signed_catalog) != pack_id:
            raise ModelPackError("model_pack_existing_identity_changed")
        for release in registry.releases.values():
            registry.select(release.model_id, allow_test_only=False)
            registry.bindings[release.release_id].verify(root)
        return registry

    @staticmethod
    def _start_transaction(state, kind, pack_id, scope, **details):
        state["transaction"] = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "pack_id": pack_id,
            "owner_scope": owner_digest(scope),
            "prior_active": state["active"],
            "prior_previous": state["previous"],
            **details,
        }

    def _finish_transaction(self, state, *, scope, audit):
        """Replay an intent forward. A pending journal always blocks worker load.

        The trust high-water mark is NEVER rolled back, even if the pointer,
        audit completion, or final encrypted-state write fails. Recovery must
        satisfy today's signature/revocation policy again.
        """
        transaction = state["transaction"]
        pack_id = transaction["pack_id"]
        if transaction["owner_scope"] != owner_digest(scope):
            raise ModelPackError("model_pack_transaction_unavailable", 404)
        kind = transaction["kind"]
        if kind == "activate":
            abandoned = transaction.get("deactivate", False)
            if not abandoned:
                registry = self._verify_pack(pack_id)
                self.authority.verify(
                    registry.signed_catalog,
                    releases=registry.release_document,
                    artifacts=registry.artifact_document,
                )
            active = "" if abandoned else pack_id
            atomic_write_bytes(
                external_root(self.root / "active.json"),
                canonical({"schema": "fi_active_pack_v1", "pack_id": active}),
            )
            audit(
                "model_pack_activation_deactivated"
                if abandoned
                else "model_pack_activation_completed",
                digest(transaction),
            )
            state.update(
                active=active,
                previous=(
                    transaction["prior_active"]
                    if transaction["prior_active"] != active
                    else transaction["prior_previous"]
                ),
            )
            job_id = transaction.get("job_id")
            if job_id and job_id in state["jobs"]:
                state["jobs"][job_id].update(
                    status="canceled" if abandoned else "activated",
                    error="model_pack_activation_deactivated" if abandoned else "",
                )
        else:
            trash_id = transaction.get("trash_id", transaction["id"])
            if not _ID.fullmatch(str(trash_id)):
                raise ModelPackError("model_pack_transaction_path_invalid")
            installed = external_root(self.root / "packs" / pack_id)
            archived = external_root(self.root / "trash" / trash_id)
            if installed.parent != self.root / "packs" or archived.parent != self.root / "trash":
                raise ModelPackError("model_pack_transaction_path_invalid")
            source, target = (installed, archived) if kind == "remove" else (archived, installed)
            # Both present is ambiguous, never overwrite. Neither present is loss,
            # not successful recovery. The journal identifies exactly one move.
            if source.exists() == target.exists():
                raise ModelPackError("model_pack_transaction_files_changed")
            if transaction.get("abandon"):
                # Reverse only this journaled storage move; never load a model
                # or weaken admission. Also escapes a now-revoked restore.
                if target.exists():
                    if not target.is_dir():
                        raise ModelPackError("model_pack_transaction_files_changed")
                    os.replace(target, source)
                audit("model_pack_storage_change_abandoned", digest(transaction))
                state["transaction"] = None
                self._save(state)
                return {
                    "status": "storage_change_abandoned",
                    "pack_id": pack_id,
                    "review_required": True,
                    "original_preserved": True,
                    "network_used": False,
                    "requires_worker_restart": False,
                }
            if kind == "restore":
                self._verify_pack(pack_id, root=source if source.exists() else target)
            if source.exists():
                if not source.is_dir():
                    raise ModelPackError("model_pack_transaction_files_changed")
                os.replace(source, target)
            audit("model_pack_" + kind + "_completed", digest(transaction))
            if kind == "remove":
                metadata = state["installed"].pop(pack_id)
                state["removed"][pack_id] = {**metadata, "trash_id": trash_id}
            else:
                metadata = state["removed"].pop(pack_id)
                state["installed"][pack_id] = {
                    key: value for key, value in metadata.items() if key != "trash_id"
                }
        state["transaction"] = None
        self._save(state)
        return {
            "status": "deactivated"
            if kind == "activate" and transaction.get("deactivate")
            else kind + "_completed",
            "pack_id": pack_id,
            "review_required": True,
            "network_used": False,
            "requires_worker_restart": kind == "activate",
            "original_preserved": True,
            "disk_space_reclaimed": False,
        }

    def recover(self, *, scope, audit, transaction_id, deactivate=False, abandon=False):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            transaction = state["transaction"]
            if (
                not transaction
                or transaction["id"] != transaction_id
                or transaction["owner_scope"] != owner_digest(scope)
            ):
                raise ModelPackError("model_pack_transaction_unavailable", 404)
            if (
                (deactivate and transaction["kind"] != "activate")
                or (abandon and transaction["kind"] == "activate")
                or (deactivate and abandon)
            ):
                raise ModelPackError("model_pack_recovery_action_invalid")
            audit(
                "model_pack_recovery_authorized",
                digest(
                    {"transaction_id": transaction_id, "deactivate": deactivate, "abandon": abandon}
                ),
            )
            if deactivate:
                # Persist the deactivation intent before changing anything. A
                # failed deactivation cannot be accidentally replayed as activate.
                transaction["deactivate"] = True
                self._save(state)
            if abandon:
                transaction["abandon"] = True
                self._save(state)
            return self._finish_transaction(state, scope=scope, audit=audit)

    def activate_installed(self, *, scope, audit, pack_id, expected_active, previous_only=False):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            self._owned_pack(state, pack_id, scope)
            if (previous_only and state["previous"] != pack_id) or state[
                "active"
            ] != expected_active:
                raise ModelPackError("model_pack_activation_consent_changed")
            self._verify_pack(pack_id)  # Old sequence, expired or revoked? Refuse.
            audit("model_pack_installed_activation_authorized", pack_id)
            self._start_transaction(state, "activate", pack_id, scope)
            self._save(state)
            return self._finish_transaction(state, scope=scope, audit=audit)

    def reactivate_previous(self, **kwargs):
        return self.activate_installed(**kwargs, previous_only=True)

    @staticmethod
    def _owned_pack(state, pack_id, scope, *, removed=False):
        row = state["removed" if removed else "installed"].get(pack_id)
        if not row or row.get("owner_scope") != owner_digest(scope):
            raise ModelPackError("model_pack_unavailable", 404)
        return row

    def remove(self, *, scope, audit, pack_id):
        """Recoverable archive of an inactive, unreferenced, whole pack only."""
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            self._owned_pack(state, pack_id, scope)
            if pack_id in {state["active"], state["previous"]} or any(
                row.get("pack_id") == pack_id and row["status"] in _ACTIVE_STATES
                for row in state["jobs"].values()
            ):
                raise ModelPackError("model_pack_still_referenced")
            if len(state["removed"]) >= 32:
                raise ModelPackError("model_pack_store_capacity")
            audit("model_pack_remove_authorized", pack_id)
            self._start_transaction(state, "remove", pack_id, scope)
            self._save(state)
            return self._finish_transaction(state, scope=scope, audit=audit)

    def restore(self, *, scope, audit, pack_id):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._owned_pack(state, pack_id, scope, removed=True)
            if len(list((self.root / "packs").iterdir())) >= 16:
                raise ModelPackError("model_pack_store_capacity")
            self._verify_pack(pack_id, root=external_root(self.root / "trash" / row["trash_id"]))
            audit("model_pack_restore_authorized", pack_id)
            self._start_transaction(state, "restore", pack_id, scope, trash_id=row["trash_id"])
            self._save(state)
            return self._finish_transaction(state, scope=scope, audit=audit)

    def registry(self, root, *, inspection=False):
        return HotSwapRegistry.load(
            root=root,
            release_registry=root / "releases.json",
            artifact_registry=root / "artifacts.json",
            admission_catalog=root / "admission.json",
            admission_authority=self.authority.inspection_only() if inspection else self.authority,
        )

    def discard(self, job_id, *, scope, audit):
        with self.lock, exclusive_file_lock(self.root / ".packs.lock"):
            state = self._load()
            self._idle(state)
            row = self._job(state, job_id, scope)
            if row["status"] in {"resuming", "verifying", "canceling", "activating"}:
                raise ModelPackError("model_pack_discard_busy_or_active")
            audit("model_pack_partial_discarded", digest({"job_id": job_id}))
            # Only this generated, validated upload ID is removed; never pack,
            # trust, active state, original file, or arbitrary caller paths.
            target = external_root(self.root / "uploads" / job_id)
            if target.parent != self.root / "uploads":
                raise ModelPackError("model_pack_discard_path_invalid")
            if target.exists():
                shutil.rmtree(target)
            del state["jobs"][job_id]
            self._save(state)
            return {"status": "discarded", "original_preserved": True, "review_required": True}

    def inventory(self, *, scope):
        with self.lock:
            state = self._load()
            jobs = [
                self._public(self._job(state, key, scope))
                for key, row in state["jobs"].items()
                if row["scope"] == digest(scope)
            ]
            owner = owner_digest(scope) if scope.get("role") == "admin" else None
            recoverable = [
                self._public(row)
                for row in state["jobs"].values()
                if row["scope"] != digest(scope)
                and row.get("owner_scope") == owner
                and row["status"]
                in {
                    "uploading",
                    "resuming",
                    "verifying",
                    "canceling",
                    "interrupted",
                    "canceled",
                    "failed",
                    "ready_to_activate",
                    "activated",
                }
            ]
            transaction = state["transaction"]
            models, error = [], "model_pack_transaction_recovery_required" if transaction else ""
            if state["active"] and not transaction:
                try:
                    registry = load_active_pack(self.root, self.authority)
                    if digest(registry.signed_catalog) != state["active"]:
                        raise ModelPackError("model_pack_activation_recovery_required")
                    models = [
                        registry.select(row.model_id, allow_test_only=False).public()
                        for row in registry.releases.values()
                    ]
                except Exception:
                    error = "model_pack_active_admission_unavailable"
            return {
                "status": "blocked" if error else "configured",
                "error": error,
                "active_pack_id": state["active"],
                "previous_pack_id": state["previous"],
                "models": models,
                "jobs": jobs,
                "recoverable_jobs": recoverable,
                "transaction": (
                    {key: transaction[key] for key in ("id", "kind", "pack_id")}
                    | {"deactivating": bool(transaction.get("deactivate"))}
                    if transaction and transaction["owner_scope"] == owner
                    else None
                ),
                "installed": [
                    {
                        "pack_id": key,
                        "summary": row["summary"],
                        "active": key == state["active"],
                        "previous": key == state["previous"],
                    }
                    for key, row in state["installed"].items()
                    if row.get("owner_scope") == owner
                ],
                "removed": [
                    {"pack_id": key, "summary": row["summary"]}
                    for key, row in state["removed"].items()
                    if row.get("owner_scope") == owner
                ],
                "max_pack_bytes": MAX_PACK_BYTES,
                "chunk_bytes": CHUNK_BYTES,
                "downloads_enabled": False,
                "network_used": False,
                "review_required": True,
            }


def load_active_pack(root: Path, authority: AdmissionAuthority) -> HotSwapRegistry:
    root = external_root(root)
    # Loading is serialized with pointer/journal commits across app processes.
    with exclusive_file_lock(root / ".packs.lock"):
        return _load_active_pack_locked(root, authority)


def _load_active_pack_locked(root, authority):
    state = ModelPackService(root, authority)._load()
    if state["transaction"]:
        raise ModelPackError("model_pack_transaction_recovery_required")
    pointer = strict_json_load_path(root / "active.json", max_bytes=4096, require_object=True)
    if (
        set(pointer) != {"schema", "pack_id"}
        or pointer["schema"] != "fi_active_pack_v1"
        or pointer["pack_id"]
        and not _HASH.fullmatch(str(pointer["pack_id"]))
    ):
        raise ModelPackError("model_pack_active_pointer_invalid")
    if pointer["pack_id"] != state["active"]:
        raise ModelPackError("model_pack_activation_recovery_required")
    if not pointer["pack_id"]:
        raise ModelPackError("model_pack_no_active_pack")
    pack = external_root(root / "packs" / pointer["pack_id"])
    registry = HotSwapRegistry.load(
        root=pack,
        release_registry=pack / "releases.json",
        artifact_registry=pack / "artifacts.json",
        admission_catalog=pack / "admission.json",
        admission_authority=authority,
    )
    if digest(registry.signed_catalog) != pointer["pack_id"]:
        raise ModelPackError("model_pack_active_identity_mismatch")
    return registry
