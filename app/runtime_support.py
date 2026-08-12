from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from legal.security.durable_io import (
    DurableIOError,
    atomic_write_bytes,
    durable_append_text,
    exclusive_file_lock,
)
from maine_family_law_llm.version import FORK_GUIDE_RELATIVE_PATH, PRIVACY_POLICY_RELATIVE_PATH

RUNTIME_MODE_ENV = "MFL_RUNTIME_MODE"
API_STATE_PATH_ENV = "MFL_LOCAL_API_STATE_PATH"
CASE_LIBRARY_PATH_ENV = "MFL_CASE_LIBRARY_PATH"
RUNTIME_LOG_DIR_ENV = "MFL_RUNTIME_LOG_DIR"
AUTHORITY_DATA_ROOT_ENV = "MFL_AUTHORITY_DATA_ROOT"
_RUNTIME_LOG_MAX_BYTES = 512 * 1024
_RUNTIME_LOG_MESSAGE_MAX_BYTES = 16 * 1024
_VALID_RUNTIME_MODES = frozenset({"source", "store"})


@dataclass(frozen=True)
class RuntimeContext:
    mode: str
    bundle_root: Path
    writable_root: Path
    logs_root: Path
    runtime_data_root: Path
    case_library_path: Path
    api_state_path: Path
    first_run_marker: Path
    is_frozen: bool

    @property
    def is_store_runtime(self) -> bool:
        return self.mode == "store"

    @property
    def allows_repo_bootstrap_writes(self) -> bool:
        return self.mode == "source"

    def repo_path(self, relative: str) -> Path:
        return self.bundle_root / relative


def _local_appdata_root() -> Path:
    base = os.environ.get("LOCALAPPDATA", "").strip()
    if base:
        candidate = Path(base).expanduser()
        # Local runtime state must not be redirected into a bundle-relative or
        # network location by a malformed inherited environment variable.
        if candidate.is_absolute() and not str(candidate).startswith("\\\\"):
            return candidate
    return Path.home() / "AppData" / "Local"


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parents[1]


def build_runtime_context(mode: str | None = None) -> RuntimeContext:
    detected_mode = "store" if getattr(sys, "frozen", False) else "source"
    raw_mode = mode if mode is not None else os.environ.get(RUNTIME_MODE_ENV, "")
    requested_mode = str(raw_mode or "").strip().lower() or detected_mode
    if requested_mode not in _VALID_RUNTIME_MODES:
        raise ValueError("Runtime mode must be 'source' or 'store'.")
    resolved_mode = requested_mode
    root = bundle_root()
    local_root = _local_appdata_root() / "MaineFamilyLawLLM"
    writable_root = local_root if resolved_mode == "store" else root
    logs_root = local_root / "logs"
    # A source launcher and an installed MSIX can run at the same time.  They
    # must not share API state or a writable corpus location: otherwise the
    # Store smoke test can attach to a source-process loopback service.
    runtime_data_root = local_root / "runtime_data" / resolved_mode
    case_library_path = local_root / "case_library.json"
    api_state_path = local_root / "state" / f"local_api-{resolved_mode}.json"
    first_run_marker = local_root / "state" / "first_run_complete.json"
    return RuntimeContext(
        mode=resolved_mode,
        bundle_root=root,
        writable_root=writable_root,
        logs_root=logs_root,
        runtime_data_root=runtime_data_root,
        case_library_path=case_library_path,
        api_state_path=api_state_path,
        first_run_marker=first_run_marker,
        is_frozen=bool(getattr(sys, "frozen", False)),
    )


def configure_runtime_environment(context: RuntimeContext) -> RuntimeContext:
    if context.is_store_runtime:
        context.logs_root.mkdir(parents=True, exist_ok=True)
        context.runtime_data_root.mkdir(parents=True, exist_ok=True)
        context.case_library_path.parent.mkdir(parents=True, exist_ok=True)
        context.api_state_path.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the read-only external authority product independently from
        # writable matter/runtime state.  Historically both used
        # MAINE_FAMILY_LAW_DATA_ROOT, causing a frozen Store launch to hide a
        # configured authority build when it redirected private state into
        # LocalAppData.
        configured_authority = str(
            os.environ.get(AUTHORITY_DATA_ROOT_ENV)
            or os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT")
            or (context.writable_root / "authority-data")
        ).strip()
        os.environ[AUTHORITY_DATA_ROOT_ENV] = configured_authority
        os.environ["MAINE_FAMILY_LAW_DATA_ROOT"] = str(context.runtime_data_root)
        os.environ[CASE_LIBRARY_PATH_ENV] = str(context.case_library_path)
        os.environ[API_STATE_PATH_ENV] = str(context.api_state_path)
        os.environ[RUNTIME_LOG_DIR_ENV] = str(context.logs_root)
    os.environ[RUNTIME_MODE_ENV] = context.mode
    return context


def open_path_or_url(target: Path | str) -> None:
    os.startfile(str(target))


def append_runtime_log(context: RuntimeContext, message: str) -> Path:
    path = context.logs_root / "store-runtime.log"
    try:
        context.logs_root.mkdir(parents=True, exist_ok=True)
        # Serialize retention and appends. A diagnostic path is user-private
        # state and must not be redirected through a link or grow without cap.
        with exclusive_file_lock(path.with_suffix(".log.lock")):
            if path.exists() and path.is_symlink():
                raise DurableIOError("runtime_log_symlink_refused")
            if path.exists() and not path.is_file():
                raise DurableIOError("runtime_log_regular_file_required")
            if path.exists() and path.stat().st_size >= _RUNTIME_LOG_MAX_BYTES:
                atomic_write_bytes(
                    path,
                    b"Previous runtime diagnostics exceeded the retention limit "
                    b"and were cleared.\n",
                    mode=0o600,
                )
            entry = str(message).rstrip().encode("utf-8", errors="backslashreplace")
            if len(entry) > _RUNTIME_LOG_MESSAGE_MAX_BYTES:
                entry = entry[:_RUNTIME_LOG_MESSAGE_MAX_BYTES] + b"\n[diagnostic entry truncated]"
            durable_append_text(path, entry.decode("utf-8", errors="replace") + "\n")
    except (DurableIOError, OSError) as exc:
        raise RuntimeError("The private runtime diagnostic log cannot be written safely.") from exc
    return path


def log_exception(context: RuntimeContext, exc: BaseException) -> Path:
    payload = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return append_runtime_log(context, payload)


def local_about_links(context: RuntimeContext) -> dict[str, Path]:
    return {
        "fork_guide": context.repo_path(FORK_GUIDE_RELATIVE_PATH),
        "privacy_policy": context.repo_path(PRIVACY_POLICY_RELATIVE_PATH),
    }
