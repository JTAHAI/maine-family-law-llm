from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_support import RuntimeContext, append_runtime_log, configure_runtime_environment
from maine_family_law_llm.version import VERSION

DEFAULT_PORT_CANDIDATES = (8000, 8011, 8012, 8013)


@dataclass(frozen=True)
class LocalServiceStatus:
    url: str
    port: int
    pid: int | None
    started_now: bool
    healthy: bool


def _state_file(context: RuntimeContext) -> Path:
    return context.api_state_path


def _load_state(context: RuntimeContext) -> dict[str, Any]:
    path = _state_file(context)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_state(context: RuntimeContext, payload: dict[str, Any]) -> Path:
    path = _state_file(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _service_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _health_payload(port: int, timeout: float = 1.5) -> dict[str, Any] | None:
    request = urllib.request.Request(_health_url(port), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _ping_health(port: int, timeout: float = 1.5) -> bool:
    return _health_payload(port, timeout=timeout) is not None


def _service_matches_runtime_version(port: int, timeout: float = 1.5) -> bool:
    payload = _health_payload(port, timeout=timeout)
    return bool(payload and payload.get("status") == "ok" and payload.get("version") == VERSION)


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _candidate_ports(context: RuntimeContext) -> list[int]:
    candidates = list(DEFAULT_PORT_CANDIDATES)
    saved_port = int(_load_state(context).get("port", 0) or 0)
    if saved_port and saved_port not in candidates:
        candidates.insert(0, saved_port)
    return candidates


def _wait_for_service(port: int, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _ping_health(port):
            return True
        time.sleep(0.35)
    return False


def _child_env(context: RuntimeContext) -> dict[str, str]:
    env = dict(os.environ)
    env["MFL_RUNTIME_MODE"] = context.mode
    env["MAINE_FAMILY_LAW_DATA_ROOT"] = str(context.runtime_data_root)
    env["MFL_CASE_LIBRARY_PATH"] = str(context.case_library_path)
    env["MFL_LOCAL_API_STATE_PATH"] = str(context.api_state_path)
    env["MFL_RUNTIME_LOG_DIR"] = str(context.logs_root)
    return env


def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _service_command(context: RuntimeContext, port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--serve-local-api", "--port", str(port)]
    return [sys.executable, str(context.bundle_root / "app" / "store_entrypoint.py"), "--serve-local-api", "--port", str(port)]


def ensure_local_service(context: RuntimeContext) -> LocalServiceStatus:
    configure_runtime_environment(context)
    state = _load_state(context)
    prior_port = int(state.get("port", 0) or 0)
    prior_pid = int(state.get("pid", 0) or 0) or None
    if prior_port and _service_matches_runtime_version(prior_port):
        return LocalServiceStatus(url=_service_url(prior_port), port=prior_port, pid=prior_pid, started_now=False, healthy=True)

    for port in _candidate_ports(context):
        if not _port_is_free(port):
            continue
        command = _service_command(context, port)
        append_runtime_log(context, f"Starting local API service: {' '.join(command)}")
        proc = subprocess.Popen(
            command,
            cwd=str(context.bundle_root),
            env=_child_env(context),
            creationflags=_creationflags(),
        )
        if _wait_for_service(port):
            _write_state(
                context,
                {
                    "port": port,
                    "pid": proc.pid,
                    "url": _service_url(port),
                    "bundle_root": str(context.bundle_root),
                    "mode": context.mode,
                },
            )
            return LocalServiceStatus(url=_service_url(port), port=port, pid=proc.pid, started_now=True, healthy=True)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
    raise RuntimeError("The local chat service could not be started on a loopback port.")


def stop_local_service(context: RuntimeContext) -> bool:
    state = _load_state(context)
    pid = int(state.get("pid", 0) or 0)
    port = int(state.get("port", 0) or 0)
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True, text=True, timeout=15)
        else:
            os.kill(pid, signal.SIGTERM)
        if port and _wait_for_service(port, timeout_seconds=2):
            return False
    finally:
        try:
            _state_file(context).unlink(missing_ok=True)
        except Exception:
            pass
    return True


def run_local_service(port: int, context: RuntimeContext) -> int:
    configure_runtime_environment(context)
    context.logs_root.mkdir(parents=True, exist_ok=True)
    append_runtime_log(context, f"Serving local API on 127.0.0.1:{port}")
    from maine_family_law_llm.api import app
    import uvicorn

    # Windowed PyInstaller applications may have sys.stdout and sys.stderr set
    # to None. Uvicorn's default formatter calls stderr.isatty(), which causes
    # the Microsoft Store runtime to terminate before the local API can start.
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
        log_config=None,
    )
    return 0
