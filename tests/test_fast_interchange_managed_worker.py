import json
import os
import secrets

import pytest

from app.services.fast_interchange_worker_service import (
    ManagedFastInterchangeWorker,
    ManagedWorkerError,
    _admitted_models,
    _device_environment,
    _worker_command,
)


def test_managed_worker_uses_bounded_cpu_settings(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 24)
    assert _device_environment({"recommended_accelerator": {"kind": "cpu"}}) == {
        "MFL_FAST_INTERCHANGE_ALLOW_CPU": "1",
        "MFL_FAST_INTERCHANGE_FORCE_CPU": "1",
        "MFL_FAST_INTERCHANGE_CPU_THREADS": "4",
    }


def test_managed_worker_uses_exact_hardware_qualified_gpu_index():
    assert _device_environment({"recommended_accelerator": {"index": 3}}) == {
        "MFL_FAST_INTERCHANGE_ALLOW_CPU": "0",
        "MFL_FAST_INTERCHANGE_FORCE_CPU": "0",
        "MFL_FAST_INTERCHANGE_CUDA_DEVICE": "3",
    }
    with pytest.raises(ManagedWorkerError, match="fast_interchange_hardware_not_ready"):
        _device_environment({"recommended_accelerator": None})


def test_source_worker_command_uses_current_interpreter(monkeypatch):
    monkeypatch.delattr("sys.frozen", raising=False)
    command = _worker_command()
    assert command[0]
    assert command[1:] == ["-m", "legal.fast_interchange.worker"]


def test_worker_identity_probe_is_authenticated(monkeypatch):
    observed = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(
                {
                    "data": [
                        {
                            "model_id": "fictional-model",
                            "release_fingerprint": "f" * 64,
                            "capability": "evidence_review",
                        }
                    ]
                }
            ).encode()

    def open_request(request, timeout):
        observed["authorization"] = request.get_header("Authorization")
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.services.fast_interchange_worker_service.urlopen", open_request)
    assert _admitted_models(8105, "secret-test-token") == [
        {
            "model_id": "fictional-model",
            "release_fingerprint": "f" * 64,
            "capability": "evidence_review",
        }
    ]
    assert observed == {"authorization": "Bearer secret-test-token", "timeout": 1.0}


def test_dead_worker_is_reaped_and_host_token_is_removed(monkeypatch):
    class ExitedProcess:
        @staticmethod
        def poll():
            return 7

    managed = ManagedFastInterchangeWorker()
    managed._process = ExitedProcess()
    test_token = secrets.token_hex(32)
    managed._token = test_token
    managed._identity = {"model_id": "dead-model"}
    monkeypatch.setenv("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", test_token)

    status = managed.public_status()

    assert status["status"] == "stopped"
    assert status["model"] == {}
    assert "MAINE_FAST_INTERCHANGE_WORKER_TOKEN" not in os.environ
