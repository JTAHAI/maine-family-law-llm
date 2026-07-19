from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from maine_family_law_llm.version import FORK_GUIDE_RELATIVE_PATH, PRIVACY_POLICY_RELATIVE_PATH

RUNTIME_MODE_ENV = "MFL_RUNTIME_MODE"
API_STATE_PATH_ENV = "MFL_LOCAL_API_STATE_PATH"
CASE_LIBRARY_PATH_ENV = "MFL_CASE_LIBRARY_PATH"
RUNTIME_LOG_DIR_ENV = "MFL_RUNTIME_LOG_DIR"


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
        return Path(base)
    return Path.home() / "AppData" / "Local"


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parents[1]


def build_runtime_context(mode: str | None = None) -> RuntimeContext:
    resolved_mode = mode or os.environ.get(RUNTIME_MODE_ENV, "").strip().lower() or ("store" if getattr(sys, "frozen", False) else "source")
    root = bundle_root()
    local_root = _local_appdata_root() / "MaineFamilyLawLLM"
    writable_root = local_root if resolved_mode == "store" else root
    logs_root = local_root / "logs"
    runtime_data_root = local_root / "runtime_data"
    case_library_path = local_root / "case_library.json"
    api_state_path = local_root / "state" / "local_api.json"
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
        os.environ["MAINE_FAMILY_LAW_DATA_ROOT"] = str(context.runtime_data_root)
        os.environ[CASE_LIBRARY_PATH_ENV] = str(context.case_library_path)
        os.environ[API_STATE_PATH_ENV] = str(context.api_state_path)
        os.environ[RUNTIME_LOG_DIR_ENV] = str(context.logs_root)
    os.environ[RUNTIME_MODE_ENV] = context.mode
    return context


def open_path_or_url(target: Path | str) -> None:
    os.startfile(str(target))


def append_runtime_log(context: RuntimeContext, message: str) -> Path:
    context.logs_root.mkdir(parents=True, exist_ok=True)
    path = context.logs_root / "store-runtime.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")
    return path


def log_exception(context: RuntimeContext, exc: BaseException) -> Path:
    payload = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return append_runtime_log(context, payload)


def local_about_links(context: RuntimeContext) -> dict[str, Path]:
    return {
        "fork_guide": context.repo_path(FORK_GUIDE_RELATIVE_PATH),
        "privacy_policy": context.repo_path(PRIVACY_POLICY_RELATIVE_PATH),
    }
