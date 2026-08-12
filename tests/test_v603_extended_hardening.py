"""v6.0.3 extended hardening regression tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import local_api_service
from app.runtime_support import RuntimeContext
from legal.release.release_candidate_operations import GAReleaseCandidateOperationsStore
from legal.security.durable_io import (
    DurableIOError,
    atomic_write_bytes,
    read_bounded_regular_file,
)
from legal.security.strict_json import StrictJSONError, strict_json_load_path
from maine_family_law_llm import api as api_module


def _context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        mode="store",
        bundle_root=tmp_path / "bundle",
        writable_root=tmp_path / "writable",
        logs_root=tmp_path / "logs",
        runtime_data_root=tmp_path / "data",
        case_library_path=tmp_path / "state" / "cases.json",
        api_state_path=tmp_path / "state" / "local_api.json",
        first_run_marker=tmp_path / "state" / "first.json",
        is_frozen=True,
    )



def test_package_shim_does_not_execute_source_text() -> None:
    root = Path(__file__).resolve().parents[1]
    shim = (root / "maine_family_law_llm" / "__init__.py").read_text(encoding="utf-8")
    assert "exec(" not in shim
    assert "from .version import VERSION" in shim

def test_secure_bounded_read_refuses_symlink_and_oversize(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text('{"ok":true}', encoding="utf-8")
    assert read_bounded_regular_file(target, max_bytes=64) == b'{"ok":true}'
    with pytest.raises(DurableIOError, match="maximum_bytes_exceeded"):
        read_bounded_regular_file(target, max_bytes=2)

    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(DurableIOError, match="regular_file_required"):
        read_bounded_regular_file(link, max_bytes=64)
    with pytest.raises(StrictJSONError, match="json_file_unavailable"):
        strict_json_load_path(link, max_bytes=64, require_object=True)


def test_atomic_private_write_refuses_symlink_destination(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("outside", encoding="utf-8")
    destination = tmp_path / "state.json"
    try:
        destination.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(DurableIOError, match="file_symlink_refused"):
        atomic_write_bytes(destination, b'{"safe":true}\n')
    assert outside.read_text(encoding="utf-8") == "outside"


def test_atomic_private_write_preserves_all_binary_bytes_on_windows(tmp_path: Path) -> None:
    destination = tmp_path / "protected-key.bin"
    payload = bytes(range(256)) * 4
    atomic_write_bytes(destination, payload)
    assert read_bounded_regular_file(destination, max_bytes=len(payload)) == payload



def test_local_health_probe_refuses_redirects() -> None:
    handler = local_api_service._NoRedirectHandler()
    request = __import__("urllib.request").request.Request("http://127.0.0.1:8000/api/health")
    assert handler.redirect_request(request, None, 302, "Found", {}, "https://example.com/") is None


def test_local_api_diagnostic_log_is_regular_and_bounded(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.logs_root.mkdir(parents=True)
    log_path = context.logs_root / "local-api.log"
    log_path.write_bytes(b"x" * (local_api_service._LOCAL_API_LOG_MAX_BYTES + 1))

    assert local_api_service._prepare_local_api_log(context) == log_path
    assert log_path.stat().st_size < local_api_service._LOCAL_API_LOG_MAX_BYTES

    link_path = context.logs_root / "local-api.log"
    link_path.unlink()
    target = context.logs_root / "outside.log"
    target.write_text("outside", encoding="utf-8")
    try:
        link_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(RuntimeError, match="not safe"):
        local_api_service._prepare_local_api_log(context)

def test_local_service_identity_requires_matching_nonce_and_pid(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    instance_id = "a" * 64
    state = {
        "port": 8011,
        "pid": 4242,
        "url": "http://127.0.0.1:8011/",
        "mode": "store",
        "instance_id": instance_id,
    }
    local_api_service._write_state(context, state)

    monkeypatch.setattr(
        local_api_service,
        "_read_health_identity",
        lambda port, timeout=1.5: {"healthy": True, "instance_id": instance_id, "pid": 4242},
    )
    assert local_api_service._state_service_is_healthy(local_api_service._load_state(context)) is True

    monkeypatch.setattr(
        local_api_service,
        "_read_health_identity",
        lambda port, timeout=1.5: {"healthy": True, "instance_id": "b" * 64, "pid": 4242},
    )
    assert local_api_service._state_service_is_healthy(local_api_service._load_state(context)) is False


def test_stop_service_never_kills_identity_mismatch(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    local_api_service._write_state(
        context,
        {
            "port": 8011,
            "pid": 4242,
            "url": "http://127.0.0.1:8011/",
            "mode": "store",
            "instance_id": "a" * 64,
        },
    )
    monkeypatch.setattr(
        local_api_service,
        "_read_health_identity",
        lambda port, timeout=1.5: {"healthy": True, "instance_id": "b" * 64, "pid": 4242},
    )
    killed: list[int] = []
    monkeypatch.setattr(local_api_service.os, "kill", lambda pid, sig: killed.append(pid))
    assert local_api_service.stop_local_service(context) is False
    assert killed == []
    assert not context.api_state_path.exists()


def test_health_response_proves_local_service_instance(monkeypatch) -> None:
    instance_id = "c" * 64
    monkeypatch.setenv("MFL_LOCAL_API_INSTANCE_ID", instance_id)
    client = TestClient(api_module.app)
    response = client.get("/api/health", headers={"host": "testserver"})
    assert response.status_code == 200
    assert response.headers["X-MFL-Service-Instance"] == instance_id
    assert int(response.headers["X-MFL-Service-Pid"]) == os.getpid()
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_pass50_ledger_is_serialized_across_processes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    release_root = tmp_path / "release"
    candidate_id = "v6-0-3-rc"
    store = GAReleaseCandidateOperationsStore(repo_root, release_root)
    candidate_version = str(store.policy["product_version"])
    store.create_candidate(
        candidate_id=candidate_id,
        version=candidate_version,
        source_repo_zip_sha256="a" * 64,
        source_repo_zip_name=f"Maine-Family-Law-LLM-v{candidate_version}-ga-release-candidate-full-source.zip",
        approved=True,
    )

    worker = """
import sys
from legal.release.release_candidate_operations import GAReleaseCandidateOperationsStore
repo, release, candidate, blocker = sys.argv[1:5]
store = GAReleaseCandidateOperationsStore(repo, release)
store.record_blocker(
    candidate_id=candidate,
    blocker_id=blocker,
    severity='P2',
    status='open',
    description_code='concurrent_hardening_probe',
    evidence_sha256=(blocker[-1] * 64),
    approved=True,
)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", worker, str(repo_root), str(release_root), candidate_id, f"blocker-{i}"],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(1, 7)
    ]
    failures: list[str] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        if process.returncode != 0:
            failures.append(f"rc={process.returncode} stdout={stdout} stderr={stderr}")
    assert failures == []

    verification = store.verify()
    assert verification["status"] == "pass"
    assert verification["row_count"] == 7
    rows = [json.loads(line) for line in store.ledger_path.read_text(encoding="utf-8").splitlines()]
    assert [row["sequence"] for row in rows] == list(range(1, 8))
    assert len({row["record_sha256"] for row in rows}) == 7
