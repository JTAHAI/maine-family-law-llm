"""Verify the truthful FAST INTERCHANGE status of one exact frozen runtime.

This verifier does not configure a worker, model artifact, token, registry, or
admission.  It launches an explicitly supplied frozen executable with a fresh
temporary local profile, requests only health and ``/api/local-agent/status``,
then terminates the process it owns.  A passing report proves that the shipped
runtime exposes the unadmitted local-worker boundary; it does not prove model
inference, legal quality, package installation, network isolation, or release
readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


FAST_INTERCHANGE_ENVIRONMENT = (
    "MFL_FAST_INTERCHANGE_ARTIFACT_ROOT",
    "MFL_FAST_INTERCHANGE_RELEASE_REGISTRY",
    "MFL_FAST_INTERCHANGE_ARTIFACT_REGISTRY",
    "MFL_FAST_INTERCHANGE_ADMISSION_CATALOG",
    "MFL_FAST_INTERCHANGE_ADMISSION_TRUST",
    "MFL_FAST_INTERCHANGE_STATE_ROOT",
    "MFL_FAST_INTERCHANGE_PACK_ROOT",
    "MAINE_FAST_INTERCHANGE_WORKER_TOKEN",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _free_port() -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])
    finally:
        listener.close()


def _request_json(url: str, *, timeout: float) -> tuple[int, dict[str, str], dict[str, Any]]:
    request = Request(
        url,
        headers={
            "X-MFL-Local-Role": "admin",
            "X-MFL-Tenant": "qa-local",
            "X-MFL-Session": "fast-interchange-frozen-status",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - literal loopback URL
        return response.status, dict(response.headers.items()), json.loads(response.read().decode("utf-8"))


def _environment(profile: Path, instance: str) -> dict[str, str]:
    environment = os.environ.copy()
    for key in FAST_INTERCHANGE_ENVIRONMENT:
        environment.pop(key, None)
    environment.update(
        {
            "LOCALAPPDATA": str(profile),
            "MAINE_FAMILY_LAW_DATA_ROOT": str(profile / "runtime"),
            "MFL_AUTHORITY_DATA_ROOT": str(profile / "empty-authority"),
            "MFL_RUNTIME_STATE_ROOT": str(profile / "state"),
            "MFL_IDEMPOTENCY_STATE_ROOT": str(profile / "idempotency"),
            "MFL_VAULT_KEY_ROOT": str(profile / "vault"),
            "MFL_LOCAL_API_INSTANCE_ID": instance,
            "MFL_RUNTIME_MODE": "store",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TLD_EXTRACT_NO_FETCH": "1",
        }
    )
    return environment


def _terminate(process: subprocess.Popen[str]) -> bool:
    if process.poll() is not None:
        return True
    process.terminate()
    try:
        process.wait(timeout=15)
        return True
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)
        return process.poll() is not None


def verify(runtime: Path) -> dict[str, Any]:
    runtime = runtime.resolve(strict=True)
    if not runtime.is_file():
        raise ValueError("runtime_executable_required")

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    instance = uuid.uuid4().hex + uuid.uuid4().hex
    summary: dict[str, Any] = {
        "schema_version": "fast_interchange_frozen_status_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "execution_level": "exact_frozen_runtime_canonical_api",
        "runtime_path": str(runtime),
        "runtime_sha256": _sha256(runtime),
        "base_url_class": "literal_loopback",
        "fictional_profile": True,
        "configured_fast_interchange_environment": False,
        "result": "blocked",
        "limitations": [
            "No worker, token, artifact registry, admission catalog, or model artifact was configured.",
            "This status check is not model inference, legal-quality, installed-MSIX, Store, or Enterprise evidence.",
        ],
    }
    with tempfile.TemporaryDirectory(prefix="mfl-fi-frozen-status-") as temporary:
        profile = Path(temporary)
        process = subprocess.Popen(
            [str(runtime), "--serve-local-api", "--port", str(port)],
            cwd=str(runtime.parent),
            env=_environment(profile, instance),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            health: tuple[int, dict[str, str], dict[str, Any]] | None = None
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    health = _request_json(f"{base_url}/api/health", timeout=3)
                    if health[0] == 200:
                        break
                except (OSError, URLError, TimeoutError, json.JSONDecodeError):
                    time.sleep(0.5)
            if health is None or health[0] != 200:
                raise RuntimeError("frozen_runtime_health_unavailable")
            status_code, _headers, payload = _request_json(f"{base_url}/api/local-agent/status", timeout=10)
            providers = payload.get("supported_providers")
            fast = [item for item in providers if isinstance(item, dict) and item.get("provider_id") == "fast_interchange_local"] if isinstance(providers, list) else []
            summary["health_http_status"] = health[0]
            health_headers = {str(key).casefold(): value for key, value in health[1].items()}
            summary["service_instance_matches"] = health_headers.get("x-mfl-service-instance") == instance
            summary["local_agent_http_status"] = status_code
            summary["fast_interchange_provider_count"] = len(fast)
            summary["fast_interchange_status"] = fast[0] if len(fast) == 1 else None
            summary["local_agent_boundary"] = {
                name: payload.get(name)
                for name in (
                    "enabled_by_default",
                    "loopback_only",
                    "literal_loopback_ip_required",
                    "remote_providers_enabled",
                    "exact_manifest_approval_required",
                    "server_rehydrated_sources_required",
                    "single_use_session_approval_required",
                    "review_required",
                )
            }
            expected_fast = {
                "default_endpoint": "http://127.0.0.1:8105",
                "requires_host_worker_token": True,
                "bundled_model_artifacts": False,
                "external_admission_required": True,
            }
            status_matches = (
                len(fast) == 1
                and all(fast[0].get(key) == value for key, value in expected_fast.items())
                and payload.get("enabled_by_default") is False
                and payload.get("loopback_only") is True
                and payload.get("remote_providers_enabled") is False
                and payload.get("exact_manifest_approval_required") is True
                and payload.get("review_required") is True
            )
            summary["result"] = "pass_truthful_unadmitted_state" if status_matches else "fail_status_contract"
        finally:
            summary["owned_runtime_stopped"] = _terminate(process)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = verify(arguments.runtime_executable)
    except Exception as exc:  # noqa: BLE001 - safe evidence for an owned QA runtime
        report = {
            "schema_version": "fast_interchange_frozen_status_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "execution_level": "exact_frozen_runtime_canonical_api",
            "result": "blocked",
            "safe_error": exc.__class__.__name__,
        }
    arguments.evidence.parent.mkdir(parents=True, exist_ok=True)
    arguments.evidence.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("result") == "pass_truthful_unadmitted_state" else 1


if __name__ == "__main__":
    raise SystemExit(main())
