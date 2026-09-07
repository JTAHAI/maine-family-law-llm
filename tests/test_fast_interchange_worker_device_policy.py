import pytest

from app.services.fast_interchange_worker_service import _device_environment
from legal.fast_interchange.worker import (
    FastInterchangeError,
    TransformersPeftAdapterBackend,
    _backend_options_from_environment,
)


def test_worker_device_policy_defaults_to_accelerator(monkeypatch):
    for name in (
        "MFL_FAST_INTERCHANGE_ALLOW_CPU",
        "MFL_FAST_INTERCHANGE_FORCE_CPU",
        "MFL_FAST_INTERCHANGE_CUDA_DEVICE",
        "MFL_FAST_INTERCHANGE_CPU_THREADS",
    ):
        monkeypatch.delenv(name, raising=False)
    assert _backend_options_from_environment() == {
        "allow_cpu": False,
        "force_cpu": False,
        "cuda_device": 0,
    }


def test_explicit_cpu_fallback_is_consistent_with_hardware_gate(monkeypatch):
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_ALLOW_CPU", "1")
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_FORCE_CPU", "1")
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_CPU_THREADS", "4")
    assert _backend_options_from_environment() == {
        "allow_cpu": True,
        "force_cpu": True,
        "cuda_device": 0,
        "cpu_threads": 4,
    }


def test_launcher_cpu_policy_is_accepted_by_isolated_backend(monkeypatch):
    environment = _device_environment({"recommended_accelerator": {"kind": "cpu"}})
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    options = _backend_options_from_environment()
    backend = TransformersPeftAdapterBackend(**options)
    assert backend.allow_cpu is True
    assert backend.force_cpu is True
    assert backend.cpu_threads == 4


def test_gpu_hint_with_cpu_only_runtime_preserves_admitted_fp32_fallback(monkeypatch):
    environment = _device_environment({
        "recommended_accelerator": {"index": 1}, "execution_accelerator": {"kind": "cpu"},
        "quantization": "fp32",
    })
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    options = _backend_options_from_environment()
    assert options["allow_cpu"] is True
    assert options["force_cpu"] is True
    assert options["cpu_threads"] == 4


@pytest.mark.parametrize("precision", ["bf16", "fp16"])
def test_gpu_hint_cannot_authorize_cpu_for_half_precision(monkeypatch, precision):
    environment = _device_environment({
        "recommended_accelerator": {"index": 1}, "quantization": precision,
    })
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    assert _backend_options_from_environment()["allow_cpu"] is False


@pytest.mark.parametrize(
    ("name", "value", "code"),
    [
        ("MFL_FAST_INTERCHANGE_CUDA_DEVICE", "-1", "fast_interchange_cuda_device_invalid"),
        ("MFL_FAST_INTERCHANGE_CUDA_DEVICE", "32", "fast_interchange_cuda_device_invalid"),
        ("MFL_FAST_INTERCHANGE_CPU_THREADS", "0", "fast_interchange_cpu_threads_invalid"),
        ("MFL_FAST_INTERCHANGE_CPU_THREADS", "5", "fast_interchange_cpu_threads_invalid"),
        ("MFL_FAST_INTERCHANGE_CPU_THREADS", "many", "fast_interchange_cpu_threads_invalid"),
    ],
)
def test_worker_rejects_ambiguous_or_unbounded_device_settings(monkeypatch, name, value, code):
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_ALLOW_CPU", "1")
    monkeypatch.setenv(name, value)
    with pytest.raises(FastInterchangeError, match=code):
        _backend_options_from_environment()


def test_force_cpu_cannot_bypass_cpu_admission(monkeypatch):
    monkeypatch.delenv("MFL_FAST_INTERCHANGE_ALLOW_CPU", raising=False)
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_FORCE_CPU", "1")
    with pytest.raises(
        FastInterchangeError, match="fast_interchange_force_cpu_requires_cpu_admission"
    ):
        _backend_options_from_environment()
