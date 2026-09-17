"""Research-only resident ranker over private bounded pipes, never a public server.

Windows kernel ownership is installed before the child imports model libraries.
This is not a frozen-app entrypoint or signed production admission.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import math
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from threading import Event, Lock, Thread

import psutil

from legal.security.strict_json import strict_json_loads

from .admission import canonical
from .compact_cpu import MAX_MODEL_BYTES, MAX_RESIDENT_BYTES, PinnedFile, _WindowsWorkerJob, fail
from .compact_network_guard import GUARD_VERSION
from .compact_reranker import rank_input
from .compact_source_imports import (
    SOURCE_ALLOWLIST_VERSION,
    SOURCE_IMPORT_VERSION,
    SOURCE_ONLY_BOOTSTRAP,
)

MAX_PIPE_BYTES = 256_000
# -I alone still loads the base interpreter's site-packages before a venv's
# packages. -S plus explicit paths binds this child to the selected runtime and
# never executes ambient .pth/sitecustomize code. Keep the DLL handle alive.
WORKER_BOOTSTRAP = (
    SOURCE_ONLY_BOOTSTRAP + "import os,sys;from pathlib import Path;"
    "_site=Path(sys.argv[1]);"
    "sys.path[:0]=[sys.argv[2],str(_site),str(_site/'win32'),"
    "str(_site/'win32'/'lib'),str(_site/'Pythonwin')];"
    "_dll=_site/'pywin32_system32';"
    "_dll_handle=os.add_dll_directory(str(_dll)) if _dll.is_dir() else None;"
    "from legal.fast_interchange.compact_ranker_worker import main;"
    "raise SystemExit(main())"
)


def selected_runtime_site():
    """Resolve the parent's actual dependency venv, including launcher shims.

    A repo launcher may reference one existing venv using a .pth file. Do not
    execute that file in the child or accidentally select the global runtime.
    Reject mixed environments instead of silently importing a second provider.
    """
    root = Path(psutil.__file__).resolve(strict=True).parent.parent
    if root.name != "site-packages" or not (root.parents[1] / "pyvenv.cfg").is_file():
        fail("reranker_selected_runtime_invalid")
    for name in ("torch", "transformers", "safetensors", "tokenizers", "cryptography", "numpy"):
        if Path(metadata.distribution(name).locate_file("")).resolve(strict=True) != root:
            fail("reranker_mixed_runtime_forbidden")
    return root


ERROR_PHASES = frozenset(
    {
        "protocol",
        "idle",
        "artifact_verification",
        "runtime_import",
        "model_load",
        "warm",
        "tokenize",
        "score",
    }
)
ERROR_KINDS = frozenset(
    {
        "OSError",
        "RuntimeError",
        "MemoryError",
        "ImportError",
        "ModuleNotFoundError",
        "LocalModelError",
        "ValueError",
        "KeyError",
        "AttributeError",
        "Error",
        "PythonNetworkDenied",
    }
)


def sanitize_failure(error, *, warm: bool):
    """No traceback, paths, arbitrary messages, or record data cross this boundary."""
    if not isinstance(error, dict) or set(error) != {"phase", "kind", "winerror", "module"}:
        return None
    phase, kind, number = error["phase"], error["kind"], error["winerror"]
    if (
        not isinstance(phase, str)
        or phase not in ERROR_PHASES
        or not isinstance(kind, str)
        or kind not in ERROR_KINDS
        or (number is not None and (type(number) is not int or not 0 <= number <= 2**31 - 1))
    ):
        return None
    result = {"phase": phase, "kind": kind, "winerror": number, "module": "unspecified"}
    # Warm-up has no matter data. Only a missing import's bounded root identifier
    # may appear, and never an exception message or file path.
    module = error["module"]
    if (
        warm
        and phase == "runtime_import"
        and kind == "ModuleNotFoundError"
        and isinstance(module, str)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", module)
    ):
        result["module"] = module
    return result


def verify_ranks(rows, packet):
    passages = packet["passages"]
    keys = {
        "source_id",
        "source_index",
        "source_sha256",
        "relevance_score",
        "score_meaning",
        "review_required",
        "truth_verified",
    }
    if not isinstance(rows, list) or len(rows) != len(passages):
        fail("reranker_response_invalid")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != keys:
            fail("reranker_response_invalid")
        index, score = row["source_index"], row["relevance_score"]
        if (
            type(index) is not int
            or not 0 <= index < len(passages)
            or index in seen
            or type(score) not in {int, float}
            or not math.isfinite(score)
        ):
            fail("reranker_response_invalid")
        expected = passages[index]
        if (
            row["source_id"] != expected["source_id"]
            or row["source_sha256"] != hashlib.sha256(expected["text"].encode()).hexdigest()
            or row["review_required"] is not True
            or row["truth_verified"] is not False
            or row["score_meaning"] != "passage_relevance_only"
        ):
            fail("reranker_response_invalid")
        seen.add(index)
    if rows != sorted(rows, key=lambda row: (-row["relevance_score"], row["source_index"])):
        fail("reranker_response_invalid")
    return rows


class IsolatedCompactRanker:
    def _bootstrap(self):
        return WORKER_BOOTSTRAP

    def __init__(
        self,
        files: tuple[PinnedFile, ...],
        *,
        scratch: Path,
        research_only: bool,
        locked_lease=None,
    ):
        if research_only is not True:
            fail("compact_production_admission_missing")
        if (
            not isinstance(files, tuple)
            or not 1 <= len(files) <= 64
            or any(not isinstance(r, PinnedFile) for r in files)
            or sum(row.bytes for row in files) >= MAX_MODEL_BYTES
        ):
            fail("reranker_inventory_invalid")
        if locked_lease is not None and not callable(getattr(locked_lease, "worker_allowlist", None)):
            fail("compact_locked_lease_invalid")
        self.files, self.scratch, self._locked_lease = files, Path(scratch), locked_lease
        self._process = self._job = None
        self._operation = Lock()
        self._cancel = Event()
        self._quarantined = False
        self._warm = False
        self.peak_resident_bytes = 0
        self.peak_private_bytes = 0
        self.completed_requests = 0
        self.worker_starts = 0
        self.last_exit_code = None
        self.last_failure = None

    def _memory(self):
        if self._process is None or self._process.poll() is not None:
            fail("reranker_worker_exited")
        memory = psutil.Process(self._process.pid).memory_info()
        resident = getattr(memory, "peak_wset", memory.rss)
        self.peak_private_bytes = max(
            self.peak_private_bytes, getattr(memory, "private", memory.vms)
        )
        self.peak_resident_bytes = max(self.peak_resident_bytes, resident)
        if resident > MAX_RESIDENT_BYTES:
            fail("resident_memory_limit_exceeded")
        if psutil.virtual_memory().available < 1024**3:
            fail("insufficient_available_memory")

    def _start(self, cancellation=None):
        if self._cancel.is_set() or (cancellation is not None and cancellation.is_set()):
            fail("generation_canceled")
        if self._quarantined:
            fail("compact_worker_quarantined")
        if self._process is not None:
            return
        if os.name != "nt" or getattr(sys, "frozen", False):
            fail("reranker_research_python_entrypoint_required")
        if psutil.virtual_memory().available < MAX_RESIDENT_BYTES + 1024**3:
            fail("insufficient_available_memory")
        for part in [self.scratch, *self.scratch.parents]:
            if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
                fail("artifact_link_forbidden")
        self.last_failure = self.last_exit_code = None
        self.scratch.mkdir(parents=True, exist_ok=True)
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
        }
        env.update(
            {
                "PATH": str(Path(sys.executable).parent),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "TEMP": str(self.scratch),
                "TMP": str(self.scratch),
                "HF_HOME": str(self.scratch),
                "TORCH_HOME": str(self.scratch),
                "XDG_CACHE_HOME": str(self.scratch),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "TOKENIZERS_PARALLELISM": "false",
                "CUDA_VISIBLE_DEVICES": "",
                "OMP_NUM_THREADS": "2",
                "MKL_NUM_THREADS": "2",
                "HF_HUB_DISABLE_PROGRESS_BARS": "1",
                # getpass.getuser otherwise falls back to Unix-only pwd when
                # all identity variables are scrubbed on Windows. Never pass
                # the person's real username/profile into this worker.
                "USERNAME": "mfl-ranker-worker",
                "USERPROFILE": str(self.scratch),
                "APPDATA": str(self.scratch),
                "LOCALAPPDATA": str(self.scratch),
            }
        )
        try:
            self._job = _WindowsWorkerJob()
            # A Windows venv python.exe may be a redirector that creates another
            # process. Launch the current real interpreter, with only this
            # trusted runtime's site-packages, so the one-process quota holds.
            interpreter = psutil.Process().exe()
            allowlist = ()
            if self._locked_lease is not None:
                # The lease creates this document from locked inventory rows and
                # retains a deny-write/delete handle until this worker stops.
                path, checksum = self._locked_lease.worker_allowlist(self.scratch)
                allowlist = (path, checksum)
            if self._cancel.is_set() or (cancellation is not None and cancellation.is_set()):
                fail("generation_canceled")
            self._process = subprocess.Popen(
                [
                    interpreter,
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    self._bootstrap(),
                    str(selected_runtime_site()),
                    str(Path(__file__).resolve().parents[2]),
                    *allowlist,
                ],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW | 0x00000004,
            )
            self._job.attach_and_resume(self._process)
            self.worker_starts += 1
        except BaseException:
            self._stop()
            raise

    def _stop(self):
        self._warm = False
        process, job = self._process, self._job
        try:
            if job is not None:
                job.close()
                self._job = None
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                self.last_exit_code = process.returncode
                for pipe in (process.stdin, process.stdout):
                    if pipe is not None:
                        pipe.close()
                native_handle = getattr(process, "_handle", None)
                if native_handle is not None:
                    native_handle.Close()
            self._process = None
        except BaseException:
            self._quarantined = True  # retain the owned process handle for cleanup
            raise

    def _exchange(self, action, arguments, *, timeout=60, cancellation=None):
        request_id = uuid.uuid4().hex
        request_hash = hashlib.sha256(canonical(arguments)).hexdigest()
        data = (
            canonical(
                {
                    "action": action,
                    "request_id": request_id,
                    "request_sha256": request_hash,
                    "arguments": arguments,
                }
            )
            + b"\n"
        )
        if len(data) > MAX_PIPE_BYTES:
            fail("reranker_request_too_large")
        done, result = Event(), []
        process = self._process

        def transfer():
            try:
                remaining = memoryview(data)
                while remaining:
                    written = process.stdin.write(remaining)
                    if not written:
                        raise OSError("closed private pipe")
                    remaining = remaining[written:]
                process.stdin.flush()
                result.append(process.stdout.readline(MAX_PIPE_BYTES + 1))
            except Exception:
                result.append(b"")
            finally:
                done.set()

        thread = Thread(target=transfer, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + timeout
            while not done.wait(0.025):
                if self._cancel.is_set() or (cancellation is not None and cancellation.is_set()):
                    fail("generation_canceled")
                self._memory()
                if time.monotonic() > deadline:
                    fail("generation_timeout")
            if self._cancel.is_set() or (cancellation is not None and cancellation.is_set()):
                fail("generation_canceled")
            if not result or len(result[0]) > MAX_PIPE_BYTES or not result[0].endswith(b"\n"):
                fail("reranker_response_invalid")
            try:
                body = strict_json_loads(result[0], max_bytes=MAX_PIPE_BYTES, require_object=True)
            except (TypeError, ValueError):
                fail("reranker_response_invalid")
            if (
                set(body) != {"request_id", "request_sha256", "ok", "result"}
                or body["request_id"] != request_id
                or body["request_sha256"] != request_hash
            ):
                fail("reranker_response_invalid")
            if body["ok"] is False:
                self.last_failure = sanitize_failure(body["result"], warm=action == "warm")
                if self.last_failure and self.last_failure["kind"] == "PythonNetworkDenied":
                    fail("compact_python_network_denied")
                if (
                    self.last_failure
                    and self.last_failure["phase"] == "artifact_verification"
                    and self.last_failure["kind"] in {"LocalModelError", "ValueError", "OSError"}
                ):
                    fail("compact_model_integrity_failed")
                fail("reranker_worker_failed")
            if body["ok"] is not True:
                fail("reranker_response_invalid")
            self._memory()
            return body["result"]
        except BaseException:
            self._stop()
            raise
        finally:
            thread.join(timeout=2)
            if thread.is_alive():
                self._quarantined = True
                self._stop()

    def _ensure_warm(self, cancellation=None):
        if self._warm:
            return
        # Preserve the established no-argument start seam for the normal warm
        # path; pass a cancellation object only when a caller supplied one.
        if cancellation is None:
            self._start()
        else:
            self._start(cancellation=cancellation)
        result = self._exchange(
            "warm",
            {
                "files": [
                    {"path": str(row.path.absolute()), "bytes": row.bytes, "sha256": row.sha256}
                    for row in self.files
                ]
            },
            timeout=90,
            cancellation=cancellation,
        )
        expected = {
            "status": "warm",
            "forward_passes": 1,
            "model_sha256": next(r.sha256 for r in self.files if r.path.suffix == ".safetensors"),
            "review_required": True,
            "production_admitted": False,
            "network_guard": GUARD_VERSION,
            "source_import_policy": (
                SOURCE_ALLOWLIST_VERSION if self._locked_lease is not None else SOURCE_IMPORT_VERSION
            ),
        }
        if result != expected:
            self._stop()
            fail("reranker_warm_invalid")
        self._warm = True

    def warm(self):
        if not self._operation.acquire(blocking=False):
            fail("worker_busy")
        self._cancel.clear()
        try:
            self._ensure_warm()
            return {"status": "warm", "review_required": True, "production_admitted": False}
        except BaseException:
            self._stop()
            raise
        finally:
            self._operation.release()

    def rank(self, *, query, passages, matter_id, cancellation=None):
        packet = rank_input(query, passages, matter_id)
        if not self._operation.acquire(blocking=False):
            fail("worker_busy")
        self._cancel.clear()
        try:
            if cancellation is not None and cancellation.is_set():
                fail("generation_canceled")
            self._ensure_warm(cancellation)
            if rank_input(query, passages, matter_id) != packet:
                fail("reranker_source_changed")
            rows = self._exchange("rank", packet, cancellation=cancellation)
            if cancellation is not None and cancellation.is_set():
                self._stop()
                fail("generation_canceled")
            if rank_input(query, passages, matter_id) != packet:
                fail("reranker_source_changed")
            verify_ranks(rows, packet)
            self.completed_requests += 1
            return rows
        except BaseException:
            self._stop()
            raise
        finally:
            self._operation.release()

    def cancel(self):
        self._cancel.set()
        if self._operation.acquire(blocking=False):
            try:
                self._stop()
            finally:
                self._operation.release()

    def close(self):
        self.cancel()
        if not self._operation.acquire(timeout=8):
            self._quarantined = True
            fail("reranker_close_pending")
        try:
            self._stop()
        finally:
            self._operation.release()
