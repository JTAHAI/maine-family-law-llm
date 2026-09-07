"""Explicit, loopback-only lifecycle for an admitted FAST INTERCHANGE worker."""

from __future__ import annotations

import atexit
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from legal.fast_interchange.hardware import assess_specialist_hardware, installed_torch_runtime
from legal.fast_interchange.host import load_operator_registry, release_identity
from legal.fast_interchange.worker import FastInterchangeError
from legal.model_orchestration.hardware import profile_hardware

WORKER_PORT = 8105


class ManagedWorkerError(RuntimeError):
    def __init__(self, code: str, status_code: int = 409):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--fast-interchange-worker"]
    return [sys.executable, "-m", "legal.fast_interchange.worker"]


def _port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def _health(port: int) -> dict[str, Any]:
    try:
        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as response:
            if response.status != 200:
                return {}
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _admitted_models(port: int, token: str) -> list[dict[str, Any]]:
    request = Request(
        f"http://127.0.0.1:{port}/v1/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=1.0) as response:
            if response.status != 200:
                return []
            payload = json.loads(response.read(256 * 1024).decode("utf-8"))
            rows = payload.get("data") if isinstance(payload, dict) else None
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _device_environment(readiness: dict[str, Any]) -> dict[str, str]:
    # Driver inventory alone does not make a CUDA device executable. Prefer
    # the accelerator verified for the installed Torch runtime.
    recommended = (
        readiness.get("execution_accelerator")
        or readiness.get("recommended_accelerator")
        or {}
    )
    if recommended.get("kind") == "cpu":
        return {
            "MFL_FAST_INTERCHANGE_ALLOW_CPU": "1",
            "MFL_FAST_INTERCHANGE_FORCE_CPU": "1",
            "MFL_FAST_INTERCHANGE_CPU_THREADS": str(max(1, min(4, (os.cpu_count() or 2) // 2))),
        }
    index = recommended.get("index")
    if not isinstance(index, int) or not 0 <= index <= 31:
        raise ManagedWorkerError("fast_interchange_hardware_not_ready")
    return {
        # Driver inventory can find a GPU even when this installed runtime is
        # CPU-only. FP32 admission and the RAM reserve were checked above; let
        # the backend use that same admitted precision when CUDA is unavailable.
        # Never silently downshift a BF16/FP16-only admission onto the CPU.
        "MFL_FAST_INTERCHANGE_ALLOW_CPU": "1" if readiness.get("quantization") == "fp32" else "0",
        "MFL_FAST_INTERCHANGE_FORCE_CPU": "0",
        "MFL_FAST_INTERCHANGE_CUDA_DEVICE": str(index),
    }


class ManagedFastInterchangeWorker:
    """Own one worker child; never downloads, discovers providers, or admits a pack."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._token = ""
        self._identity: dict[str, Any] = {}

    def _running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _clear_runtime_identity(self) -> None:
        if self._token and os.environ.get("MAINE_FAST_INTERCHANGE_WORKER_TOKEN") == self._token:
            os.environ.pop("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", None)
        self._process = None
        self._token = ""
        self._identity = {}

    def public_status(self) -> dict[str, Any]:
        with self._lock:
            running = self._running()
            if not running and self._process is not None:
                self._clear_runtime_identity()
            return {
                "schema_version": "managed_fast_interchange_worker_v1",
                "status": "running" if running else "stopped",
                "endpoint": f"http://127.0.0.1:{WORKER_PORT}",
                "model": dict(self._identity) if running else {},
                "loopback_only": True,
                "network_used": False,
                "automatic_downloads": False,
                "review_required": True,
            }

    def start(self, *, model_id: str, capability: str, repo_root: Path) -> dict[str, Any]:
        with self._lock:
            self.public_status()  # Reap any worker that exited between user actions.
            registry = load_operator_registry()
            try:
                release = registry.select(model_id, allow_test_only=False)
                identity = release_identity(registry, release)
            except FastInterchangeError as exc:
                raise ManagedWorkerError(exc.code) from exc
            if release.capability != capability:
                raise ManagedWorkerError("fast_interchange_capability_mismatch")
            readiness = assess_specialist_hardware(
                profile_hardware(repo_root).as_dict(),
                identity.get("compatibility") or {},
                runtime=installed_torch_runtime(),
            )
            if readiness["blockers"]:
                raise ManagedWorkerError("fast_interchange_hardware_not_ready")
            if self._running():
                if self._identity.get("catalog_sha256") == identity.get("catalog_sha256"):
                    return {**self.public_status(), "hardware_readiness": readiness}
                raise ManagedWorkerError("fast_interchange_worker_restart_required")
            if not _port_available(WORKER_PORT):
                raise ManagedWorkerError("fast_interchange_worker_port_unavailable")
            token = secrets.token_hex(32)
            environment = os.environ.copy()
            environment.update(_device_environment(readiness))
            environment.update(
                {
                    "MAINE_FAST_INTERCHANGE_WORKER_TOKEN": token,
                    "MFL_FAST_INTERCHANGE_HOST": "127.0.0.1",
                    "MFL_FAST_INTERCHANGE_PORT": str(WORKER_PORT),
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                }
            )
            process = subprocess.Popen(
                _worker_command(),
                cwd=str(repo_root),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ManagedWorkerError("fast_interchange_worker_start_failed", 503)
                health = _health(WORKER_PORT)
                admitted = _admitted_models(WORKER_PORT, token)
                expected_worker = any(
                    row.get("model_id") == identity.get("model_id")
                    and row.get("release_fingerprint") == identity.get("release_fingerprint")
                    and row.get("capability") == capability
                    for row in admitted
                )
                if health.get("network") == "loopback_only" and expected_worker:
                    self._process = process
                    self._token = token
                    self._identity = {
                        key: identity.get(key)
                        for key in (
                            "model_id",
                            "capability",
                            "release_fingerprint",
                            "catalog_sha256",
                            "admission_scope",
                            "evaluation_dataset_kind",
                        )
                    }
                    os.environ["MAINE_FAST_INTERCHANGE_WORKER_TOKEN"] = token
                    return {**self.public_status(), "hardware_readiness": readiness}
                time.sleep(0.2)
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            raise ManagedWorkerError("fast_interchange_worker_start_timeout", 503)

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            self._clear_runtime_identity()
            return self.public_status()


managed_fast_interchange_worker = ManagedFastInterchangeWorker()
atexit.register(managed_fast_interchange_worker.stop)
