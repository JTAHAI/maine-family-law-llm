from __future__ import annotations

import json
import os
import re
import secrets
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

from legal.security.durable_io import DurableIOError, atomic_write_bytes
from legal.security.strict_json import StrictJSONError, strict_json_load_path

from .runtime_support import (
    AUTHORITY_DATA_ROOT_ENV,
    RuntimeContext,
    append_runtime_log,
    configure_runtime_environment,
)

DEFAULT_PORT_CANDIDATES = tuple([8000, 8011, 8012, 8013, *range(8014, 8032)])
_INSTANCE_ID_RE = re.compile(r"[0-9a-f]{64}")
_STATE_MAX_BYTES = 64 * 1024
_LOCAL_API_LOG_MAX_BYTES = 512 * 1024


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent a local health probe from following redirects off loopback."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_HEALTH_OPENER = urllib.request.build_opener(_NoRedirectHandler())


@dataclass(frozen=True)
class LocalServiceStatus:
    url: str
    port: int
    pid: int | None
    started_now: bool
    healthy: bool


def _state_file(context: RuntimeContext) -> Path:
    return context.api_state_path


def _prepare_local_api_log(context: RuntimeContext) -> Path:
    """Return a bounded, regular log destination for local-service diagnostics."""

    context.logs_root.mkdir(parents=True, exist_ok=True)
    path = context.logs_root / "local-api.log"
    if path.is_symlink():
        raise RuntimeError("The local API diagnostic log path is not safe to use.")
    if path.exists() and not path.is_file():
        raise RuntimeError("The local API diagnostic log path is not a regular file.")
    if path.exists() and path.stat().st_size > _LOCAL_API_LOG_MAX_BYTES:
        atomic_write_bytes(
            path,
            b"Previous local API diagnostics exceeded the retention limit and were cleared.\n",
            mode=0o600,
        )
    return path


def _load_state(context: RuntimeContext) -> dict[str, Any]:
    path = _state_file(context)
    if not path.exists():
        return {}
    try:
        loaded = strict_json_load_path(path, max_bytes=_STATE_MAX_BYTES, require_object=True)
    except (StrictJSONError, DurableIOError, OSError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    try:
        port = int(loaded.get("port", 0) or 0)
        pid = int(loaded.get("pid", 0) or 0)
    except (TypeError, ValueError):
        return {}
    url = str(loaded.get("url") or "")
    instance_id = str(loaded.get("instance_id") or "").strip().casefold()
    if port and not (1 <= port <= 65535):
        return {}
    if pid < 0:
        return {}
    if url and url != _service_url(port):
        return {}
    if instance_id and not _INSTANCE_ID_RE.fullmatch(instance_id):
        return {}
    return {**loaded, "port": port, "pid": pid, "instance_id": instance_id}


def _write_state(context: RuntimeContext, payload: dict[str, Any]) -> Path:
    path = _state_file(context)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        return atomic_write_bytes(path, data, mode=0o600)
    except DurableIOError as exc:
        raise RuntimeError("The local API state could not be written safely.") from exc


def _service_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _read_health_identity(port: int, timeout: float = 1.5) -> dict[str, Any]:
    request = urllib.request.Request(_health_url(port), method="GET")
    try:
        with _HEALTH_OPENER.open(request, timeout=timeout) as response:
            if response.status != 200:
                return {}
            instance_id = str(response.headers.get("X-MFL-Service-Instance") or "").strip().casefold()
            pid_text = str(response.headers.get("X-MFL-Service-Pid") or "").strip()
            try:
                pid = int(pid_text)
            except (TypeError, ValueError):
                pid = 0
            if instance_id and not _INSTANCE_ID_RE.fullmatch(instance_id):
                return {}
            return {"healthy": True, "instance_id": instance_id, "pid": pid}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {}


def _ping_health(port: int, timeout: float = 1.5) -> bool:
    return bool(_read_health_identity(port, timeout).get("healthy"))


def _state_service_is_healthy(state: dict[str, Any], timeout: float = 1.5) -> bool:
    port = int(state.get("port", 0) or 0)
    pid = int(state.get("pid", 0) or 0)
    instance_id = str(state.get("instance_id") or "").strip().casefold()
    if port <= 0 or pid <= 0 or not _INSTANCE_ID_RE.fullmatch(instance_id):
        return False
    identity = _read_health_identity(port, timeout)
    return (
        identity.get("healthy") is True
        and identity.get("instance_id") == instance_id
        and int(identity.get("pid", 0) or 0) == pid
    )


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
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


def _wait_for_service(
    port: int,
    *,
    expected_instance_id: str,
    process: subprocess.Popen[str] | None = None,
    timeout_seconds: float = 120.0,
) -> int | None:
    """Return the PID reported by the uniquely identified service.

    On Windows, a virtual-environment ``python.exe`` can be a launcher whose
    PID differs from the base interpreter that actually owns the listening
    socket.  The per-launch 256-bit instance identifier is the authoritative
    binding; persisting the PID returned with that identifier keeps later
    health checks and shutdowns aimed at the real service process.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        identity = _read_health_identity(port)
        observed_pid = int(identity.get("pid", 0) or 0)
        if identity.get("healthy") is True and identity.get("instance_id") == expected_instance_id:
            if observed_pid > 0:
                return observed_pid
        if process is not None and process.poll() is not None:
            return None
        time.sleep(0.35)
    return None


def _child_env(context: RuntimeContext, instance_id: str) -> dict[str, str]:
    env = dict(os.environ)
    env["MFL_RUNTIME_MODE"] = context.mode
    env[AUTHORITY_DATA_ROOT_ENV] = str(
        env.get(AUTHORITY_DATA_ROOT_ENV) or (context.writable_root / "authority-data")
    )
    env["MAINE_FAMILY_LAW_DATA_ROOT"] = str(context.runtime_data_root)
    env["MFL_CASE_LIBRARY_PATH"] = str(context.case_library_path)
    env["MFL_LOCAL_API_STATE_PATH"] = str(context.api_state_path)
    env["MFL_RUNTIME_LOG_DIR"] = str(context.logs_root)
    env["MFL_LOCAL_API_INSTANCE_ID"] = instance_id
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
    if prior_port and _state_service_is_healthy(state):
        return LocalServiceStatus(url=_service_url(prior_port), port=prior_port, pid=prior_pid, started_now=False, healthy=True)

    for port in _candidate_ports(context):
        if not _port_is_free(port):
            continue
        instance_id = secrets.token_hex(32)
        command = _service_command(context, port)
        api_log_path = _prepare_local_api_log(context)
        append_runtime_log(context, f"Starting local API service: {' '.join(command)}")
        with api_log_path.open("ab", buffering=0) as api_log:
            proc = subprocess.Popen(
                command,
                cwd=str(context.bundle_root),
                env=_child_env(context, instance_id),
                stdout=api_log,
                stderr=subprocess.STDOUT,
                creationflags=_creationflags(),
            )
        service_pid = _wait_for_service(
            port, expected_instance_id=instance_id, process=proc
        )
        if service_pid is not None:
            _write_state(
                context,
                {
                    "port": port,
                    "pid": service_pid,
                    "url": _service_url(port),
                    "bundle_root": str(context.bundle_root),
                    "mode": context.mode,
                    "instance_id": instance_id,
                },
            )
            return LocalServiceStatus(
                url=_service_url(port),
                port=port,
                pid=service_pid,
                started_now=True,
                healthy=True,
            )
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
        append_runtime_log(
            context, f"Local API did not become healthy; diagnostics: {api_log_path}"
        )
    raise RuntimeError("The local chat service could not be started on a loopback port.")


def stop_local_service(context: RuntimeContext) -> bool:
    state = _load_state(context)
    pid = int(state.get("pid", 0) or 0)
    port = int(state.get("port", 0) or 0)
    if pid <= 0 or port <= 0:
        _state_file(context).unlink(missing_ok=True)
        return False
    # A stale PID may have been reused by an unrelated process. Never terminate
    # it unless the responding service proves both the saved launch nonce and PID.
    if not _state_service_is_healthy(state):
        _state_file(context).unlink(missing_ok=True)
        return False
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True, text=True, timeout=15)
        else:
            os.kill(pid, signal.SIGTERM)
        instance_id = str(state.get("instance_id") or "")
        deadline = time.time() + 2.0
        while time.time() < deadline:
            identity = _read_health_identity(port, timeout=0.35)
            if not (
                identity.get("healthy") is True
                and identity.get("instance_id") == instance_id
                and int(identity.get("pid", 0) or 0) == pid
            ):
                break
            time.sleep(0.1)
        else:
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
    from app.api.production import app
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
