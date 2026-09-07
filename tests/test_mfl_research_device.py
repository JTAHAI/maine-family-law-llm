from types import SimpleNamespace

import pytest

from scripts.mfl_research_device import (
    check_gpu_headroom, configure_device, record_start_failure, research_lock,
    select_gpu, validate_torch_device, workload_conflicts,
)

UUID = "GPU-74c52c2b-927c-1904-d5bd-727d249d7ff9"


@pytest.mark.parametrize("value", ["1", "cuda:0", "GPU-74c5", "GPU-zzzzzzzz-0000-0000-0000-000000000000"])
def test_never_accept_shifting_or_partial_gpu_identity(value):
    with pytest.raises(ValueError, match="UUID"):
        select_gpu("", value)


def test_gpu_selection_and_headroom():
    assert select_gpu(f"{UUID}, RTX 3060, 7000", UUID)["name"] == "RTX 3060"
    for inventory in ("", f"{UUID}, RTX 3060, N/A", f"{UUID}, RTX 3060, 6000",
                      f"{UUID}, RTX 3060, 7000\n{UUID}, RTX 3060, 7000"):
        with pytest.raises(RuntimeError):
            select_gpu(inventory, UUID)


def test_exclude_ancestors_not_other_research_jobs():
    rows = [{"pid": 1, "name": "python.exe", "cmdline": ["python", "train_mfl_native_pilot"]},
            {"pid": 2, "name": "python.exe", "cmdline": ["python", "diagnose_mfl_prompt_framing"]},
            {"pid": 3, "name": "python.exe", "cmdline": None},
            {"pid": 4, "name": "python.exe", "cmdline": ["python", "unrelated.py"]},
            {"pid": 5, "name": "System", "cmdline": None}]
    assert workload_conflicts(rows, {1}) == [2, 3]


def test_cpu_remains_default_without_implicit_gpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "1")
    assert configure_device("cpu", None)["precision"] == "fp32"
    with pytest.raises(ValueError):
        configure_device("cpu", UUID)
    with pytest.raises(ValueError):
        configure_device("cuda", None)


@pytest.mark.parametrize("available,count,bf16,identity", [
    (False, 1, True, UUID), (True, 2, True, UUID), (True, 1, False, UUID),
    (True, 1, True, "GPU-other"),
])
def test_cuda_bf16_and_exact_identity_required(available, count, bf16, identity):
    cuda = SimpleNamespace(is_available=lambda: available, device_count=lambda: count,
                           is_bf16_supported=lambda **kw: bf16,
                           get_device_properties=lambda n: SimpleNamespace(uuid=identity))
    with pytest.raises(RuntimeError):
        validate_torch_device(SimpleNamespace(cuda=cuda), {"execution_device": "cuda:0", "gpu": {"uuid": UUID}})


@pytest.mark.parametrize("identity", [UUID, UUID.removeprefix("GPU-")])
def test_pytorch_and_nvidia_full_uuid_representations_match(identity):
    calls = []
    cuda = SimpleNamespace(is_available=lambda: True, device_count=lambda: 1,
                           is_bf16_supported=lambda **kw: True,
                           get_device_properties=lambda n: SimpleNamespace(uuid=identity),
                           reset_peak_memory_stats=lambda: calls.append("reset"))
    validate_torch_device(SimpleNamespace(cuda=cuda), {"execution_device": "cuda:0", "gpu": {"uuid": UUID}})
    assert calls == ["reset"]


@pytest.mark.parametrize("ram,vram", [(3, 7), (10, 0)])
def test_gpu_stops_when_either_headroom_is_lost(monkeypatch, ram, vram):
    import psutil
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=ram * 1024**3))
    cuda = SimpleNamespace(mem_get_info=lambda: (vram * 1024**3, 12 * 1024**3))
    with pytest.raises(RuntimeError, match="preserve"):
        check_gpu_headroom(SimpleNamespace(cuda=cuda), {
            "execution_device": "cuda:0", "remaining_system_memory_floor_bytes": 4 * 1024**3,
            "remaining_free_vram_floor_bytes": 1024**3,
        })


@pytest.mark.parametrize("training", [False, True])
def test_start_failure_is_recorded_without_overwriting_evidence(tmp_path, monkeypatch, training):
    import json
    import scripts.train_mfl_adapter_continuation as trainer
    monkeypatch.setattr(trainer, "ROOT", tmp_path)
    output = tmp_path / "dist/model-candidates/new-run"
    report = record_start_failure(output, RuntimeError("insufficient headroom"), training=training)
    receipt = output / "training-run.json" if training else output
    assert json.loads(receipt.read_text()) == report
    assert report["quality_qualified"] is False and report["models_loaded"] is False
    with pytest.raises(ValueError, match="preserve"):
        record_start_failure(output, RuntimeError("second"), training=training)
    assert json.loads(receipt.read_text()) == report
    with pytest.raises(ValueError, match="repository dist"):
        record_start_failure(tmp_path / "outside", RuntimeError("outside"), training=training)


def test_research_lock_releases_after_failure(tmp_path, monkeypatch):
    import os
    if os.name != "nt":
        pytest.skip("Windows byte-range lock")
    import scripts.train_mfl_adapter_continuation as trainer
    monkeypatch.setattr(trainer, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="intentional"):
        with research_lock():
            with pytest.raises(RuntimeError, match="holds the lock"):
                with research_lock():
                    pytest.fail("second operation admitted")
            raise ValueError("intentional")
    with research_lock():
        pass
