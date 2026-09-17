"""Windows read-locked compact file selection. No copies, signer or factory.

This verifies selected bytes, NOT native dependency closure or model quality.
Unselected files in a shared Python environment are not thereby approved to load.
The caller must retain the lease for the entire lifetime of any future worker.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .admission import AdmissionError, canonical, digest
from .compact_admission import CompactDeclarationVerifier, CompactInventory, bounded_document


def _denied(code):
    raise AdmissionError("compact_artifacts_" + code)


class _WindowsLocks:
    """Native handles avoid the CRT file-descriptor cap for dependency inventories."""

    def __init__(self, stack, check):
        if os.name != "nt":
            _denied("platform_not_qualified")
        import win32file

        self.api, self.stack, self.check = win32file, stack, check
        self.directories = set()
        self.files = set()

    def _open(self, path, *, directory):
        self.check()
        # OPEN_REPARSE_POINT inspects the entry itself. Ancestors are opened
        # and held first; deny-delete prevents their replacement/renaming.
        handle = self.api.CreateFile(
            str(path),
            0x80000000,
            3 if directory else 1,
            None,
            3,
            0x00200000 | 0x02000000,
            None,
        )
        self.stack.callback(handle.Close)
        info = self.api.GetFileInformationByHandle(handle)
        if info[0] & 0x400 or bool(info[0] & 0x10) != directory:
            _denied("link_or_type_forbidden")
        return handle, info

    def parents(self, path):
        for parent in reversed(path.parents):
            key = str(parent).casefold()
            if key not in self.directories:
                if len(self.directories) >= 32_768:
                    _denied("directory_budget_exceeded")
                self._open(parent, directory=True)
                self.directories.add(key)

    def verify_file(self, path, row):
        self.parents(path)
        handle, info = self._open(path, directory=False)
        identity = (info[4], info[8], info[9])  # volume serial + file index high/low
        if identity in self.files:
            _denied("duplicate_file_identity")
        self.files.add(identity)
        size = (info[5] << 32) | info[6]
        if size != row.bytes:
            _denied("size_mismatch")
        checksum, count = hashlib.sha256(), 0
        while count < size:
            self.check()
            _, chunk = self.api.ReadFile(handle, min(1024 * 1024, size - count))
            if not chunk:
                _denied("short_read")
            checksum.update(chunk)
            count += len(chunk)
        after = self.api.GetFileInformationByHandle(handle)
        if after[:2] + after[3:] != info[:2] + info[3:]:
            _denied("file_changed")
        if checksum.hexdigest() != row.sha256:
            _denied("hash_mismatch")


class CompactArtifactLease:
    """An immutable receipt plus a lease-derived, read-locked import policy.

    The policy is deliberately derived *after* every inventory byte has been
    checked and while the native handles remain open.  A worker never receives
    an application supplied allowlist.  This is an integrity primitive, not a
    model-admission decision.
    """

    def __init__(self, receipt, *, source_paths, locks):
        self._receipt = canonical(receipt)
        self._source_paths = tuple(source_paths)
        self._locks = locks
        self._allowlist_path = None
        self._allowlist_sha256 = None
        self._active = True

    def receipt(self):
        if not self._active:
            _denied("lease_closed")
        return bounded_document(self._receipt, max_bytes=256_000)

    def worker_allowlist(self, scratch: Path):
        """Materialize one immutable allowlist while the enclosing lease lives.

        ``scratch`` is owned by the caller and must exist below its approved
        worker scratch root.  The document handle uses read-only sharing, so a
        different process cannot replace it between its digest check in the
        child bootstrap and import execution.  The outer ExitStack releases the
        handle on cancellation, startup failure, crash cleanup, or shutdown.
        """
        if not self._active:
            _denied("lease_closed")
        scratch = Path(scratch).resolve(strict=True)
        if scratch.is_symlink() or getattr(scratch, "is_junction", lambda: False)():
            _denied("allowlist_scratch_invalid")
        target = scratch / "compact-serving-allowlist.json"
        if self._allowlist_path is not None:
            if target != self._allowlist_path:
                _denied("allowlist_scratch_changed")
            return str(target), self._allowlist_sha256
        if target.exists():
            _denied("allowlist_preexisting")
        payload = canonical(
            {"schema_version": "compact_source_allowlist_v1", "paths": list(self._source_paths)}
        )
        # Exclusive creation prevents replacing a file supplied by a caller.
        with open(target, "xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Register cleanup before doing another cancelable operation.  If a
        # cancellation arrives while the directory chain is being acquired, the
        # owned document cannot be orphaned in scratch.
        self._locks.stack.callback(lambda path: path.unlink(missing_ok=True), target)
        # Hold a native read handle with FILE_SHARE_READ only.  The helper also
        # locks the directory chain, closing the check/use rename window.
        self._locks.parents(target)
        # ExitStack is LIFO: register deletion before opening the native handle
        # so the handle closes first, then the owned, generated file disappears.
        self._locks._open(target, directory=False)
        self._allowlist_path = target
        self._allowlist_sha256 = hashlib.sha256(payload).hexdigest()
        return str(target), self._allowlist_sha256


@contextmanager
def verified_compact_artifacts(
    authority,
    envelope,
    *,
    model_inventory,
    runtime_inventory,
    roots,
    expected_model,
    expected_policies,
    release_id,
    cancellation=None,
    progress=None,
):
    """Bind a signed declaration to actual selected files under host-owned roots.

    ``expected_model`` is the code-owned name -> (bytes, sha256) pin map.
    Neither that map, roots nor expected policies may come from imported data.
    Runtime paths use explicit host root labels; no resolver/download is allowed.
    ``acquisition.json`` is the only allowed extra model file, ignored by loaders.
    Inspection does not advance rollback state; all byte checks precede advancement.
    """
    lease = None
    try:
        # Freeze caller-owned mutable documents before any filesystem access.
        envelope = bounded_document(envelope, max_bytes=256_000)
        model_doc = bounded_document(model_inventory, max_bytes=8_000_000)
        runtime_doc = bounded_document(runtime_inventory, max_bytes=8_000_000)
        policies = dict(expected_policies)
        pins = dict(expected_model)
        verifier = CompactDeclarationVerifier(authority.inspection_only())
        declared = verifier.verify(
            envelope,
            model_inventory=model_doc,
            runtime_inventory=runtime_doc,
            expected_policies=policies,
        )
        matches = [g for g in declared["grants"] if g["release_id"] == release_id]
        if len(matches) != 1:
            _denied("release_not_declared")
        grant = matches[0]
        model = CompactInventory.model_validate(model_doc)
        runtime = CompactInventory.model_validate(runtime_doc)
        if {r.path: (r.bytes, r.sha256) for r in model.files} != pins:
            _denied("code_pins_mismatch")
        notices = [
            dict(kind=kind, **r.model_dump())
            for kind, inventory in (("model", model), ("runtime", runtime))
            for r in inventory.files
            if r.role == "notice"
        ]
        if not notices or digest(notices) != grant["rights"]["notices_inventory_sha256"]:
            _denied("notices_binding_mismatch")
        anchors = {key: Path(value) for key, value in roots.items()}
        if "model" not in anchors or any(
            not path.is_absolute() or ".." in path.parts for path in anchors.values()
        ):
            _denied("root_invalid")
        if os.name != "nt":
            _denied("platform_not_qualified")
        import win32file

        if any(
            str(p).startswith("\\\\") or win32file.GetDriveType(p.anchor) != 3
            for p in anchors.values()
        ):
            _denied("nonlocal_root_forbidden")

        def check():
            if cancellation is not None and cancellation.is_set():
                _denied("canceled")

        # Reject every unresolved runtime root before reading model bytes. A bad
        # dependency binding must not trigger a costly partial verification.
        rows = []
        for kind, inventory in (("model", model), ("runtime", runtime)):
            for row in inventory.files:
                if kind == "model":
                    path = anchors["model"] / row.path
                else:
                    label, separator, relative = row.path.partition("/")
                    if not separator or label == "model" or label not in anchors:
                        _denied("runtime_root_missing")
                    path = anchors[label] / relative
                rows.append((path, row))
        with ExitStack() as stack:
            locks = _WindowsLocks(stack, check)
            verified_bytes = 0
            for index, (path, row) in enumerate(rows, 1):
                check()
                locks.verify_file(path, row)
                verified_bytes += row.bytes
                if progress is not None:
                    progress(
                        dict(
                            files_verified=index,
                            total_files=len(rows),
                            bytes_verified=verified_bytes,
                        )
                    )
            # Model roots are exact; a shared runtime remains a selected subset,
            # not an approved import/native closure. Never flatten that distinction.
            if {p.name for p in anchors["model"].iterdir()} - {"acquisition.json"} != set(pins):
                _denied("model_layout_mismatch")
            check()
            final = CompactDeclarationVerifier(authority).verify(
                envelope,
                model_inventory=model_doc,
                runtime_inventory=runtime_doc,
                expected_policies=policies,
            )
            source_paths = []
            for row in runtime.files:
                # Only runtime inventory entries rooted in the three bootstrap
                # namespaces can govern Python/native imports.  Notices and
                # model artifacts remain integrity-governed but are not import
                # candidates.
                if row.role != "runtime":
                    continue
                prefix = row.path.split("/", 1)[0]
                if prefix in {"repository", "package_runtime", "python_runtime"}:
                    source_paths.append(row.path)
            source_paths = sorted(set(source_paths))
            lease = CompactArtifactLease(
                dict(
                    schema_version="compact_locked_selection_v1",
                    catalog_sha256=final["catalog_sha256"],
                    grant_sha256=digest(grant),
                    task=grant["task"],
                    release_id=grant["release_id"],
                    model_inventory_sha256=digest(model_doc),
                    runtime_inventory_sha256=digest(runtime_doc),
                    selected_bytes=verified_bytes,
                    selected_files=len(rows),
                    artifact_bytes_verified=True,
                    windows_read_locks_held=True,
                    runtime_scope="selected_files_only",
                    native_closure_qualified=False,
                    production_admitted=False,
                    runnable=False,
                    review_required=True,
                ),
                source_paths=source_paths,
                locks=locks,
            )
            yield lease
    except AdmissionError:
        raise
    except Exception as exc:
        if lease is not None:
            raise  # Preserve an exception raised by the consumer inside the lease.
        raise AdmissionError("compact_artifacts_verification_failed") from exc
    finally:
        if lease is not None:
            lease._active = False
