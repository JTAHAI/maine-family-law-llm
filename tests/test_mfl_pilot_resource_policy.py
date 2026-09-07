from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from scripts.evaluate_mfl_adapter_pilot import check_shared_memory, evaluation_resources
from scripts.train_mfl_adapter_continuation import cpu_training_headroom, training_device


def args(**changes):
    return SimpleNamespace(
        **{"shared_host_cpu": True, "device": "cpu", "frozen_regression": False, **changes}
    )


def test_default_keeps_exclusive_workload_guard():
    guard = Mock(side_effect=RuntimeError("active workload"))
    with pytest.raises(RuntimeError, match="active workload"):
        evaluation_resources(args(shared_host_cpu=False), guard)
    guard.assert_called_once_with()


@pytest.mark.parametrize("changes", [{"device": "cuda"}, {"frozen_regression": True}])
def test_shared_host_does_not_allow_gpu_or_full_regression(changes):
    with pytest.raises(ValueError, match="CPU and development"):
        evaluation_resources(args(**changes), Mock())


def test_shared_host_requires_headroom_before_changing_priority(monkeypatch):
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=11 * 1024**3))
    process = Mock()
    monkeypatch.setattr(psutil, "Process", process)
    with pytest.raises(RuntimeError, match="12 GiB"):
        evaluation_resources(args(), Mock())
    process.assert_not_called()


def test_shared_host_is_cpu_only_low_priority_and_bounded(monkeypatch):
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=16 * 1024**3))
    monkeypatch.setattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000, raising=False)
    process = Mock()
    monkeypatch.setattr(psutil, "Process", lambda: process)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-fictional")
    guard = Mock()
    policy = evaluation_resources(args(), guard)
    guard.assert_not_called()
    process.nice.assert_called_once_with(0x4000)
    import os

    assert os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
    assert policy["max_cases"] == 8
    assert policy["cpu_threads"] == 2
    assert policy["gpu_access"] is False
    assert policy["external_processes_changed"] is False
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=3 * 1024**3))
    with pytest.raises(RuntimeError, match="preserve memory"):
        check_shared_memory(policy)


def test_priority_failure_does_not_silently_run_at_normal_priority(monkeypatch):
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=16 * 1024**3))
    monkeypatch.setattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000, raising=False)
    process = Mock()
    process.nice.side_effect = psutil.AccessDenied()
    monkeypatch.setattr(psutil, "Process", lambda: process)
    with pytest.raises(psutil.AccessDenied):
        evaluation_resources(args(), Mock())


def test_training_default_preserves_cuda_lane():
    assert training_device(SimpleNamespace()) == "cuda:0"


@pytest.mark.parametrize(
    "changes",
    [
        {"pilot": False},
        {"precision": "bf16"},
        {"batch_size": 2},
        {"train_limit": 512},
        {"train_limit": 63},
        {"gradient_checkpointing": False},
    ],
)
def test_cpu_training_rejects_unbounded_or_unsupported_configuration(changes):
    config = {
        "device": "cpu",
        "pilot": True,
        "precision": "fp32",
        "batch_size": 1,
        "train_limit": 128,
        "gradient_checkpointing": True,
        **changes,
    }
    with pytest.raises(ValueError, match="64-128-row"):
        training_device(SimpleNamespace(**config))


def test_cpu_training_configuration_and_memory_floor(monkeypatch):
    config = SimpleNamespace(
        device="cpu",
        pilot=True,
        precision="fp32",
        batch_size=1,
        train_limit=128,
        gradient_checkpointing=True,
    )
    assert training_device(config) == "cpu"
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=3 * 1024**3))
    with pytest.raises(RuntimeError, match="headroom"):
        cpu_training_headroom()
