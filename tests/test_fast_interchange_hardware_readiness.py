from legal.fast_interchange.hardware import assess_specialist_hardware

GIB = 1024**3


def profile(*, memory=16 * GIB, gpus=()):
    return {"available_memory_bytes": memory, "details": {"gpus": list(gpus)}}


def gpu(*, available, capability):
    return {
        "index": 1,
        "name": "Fictional local GPU",
        "available_vram_bytes": available,
        "compute_capability": capability,
    }


def test_bf16_readiness_requires_modern_gpu_and_headroom():
    compatibility = {"quantization": "bf16", "max_resident_bytes": 8 * GIB}
    old = assess_specialist_hardware(
        profile(gpus=[gpu(available=8 * GIB, capability=6.1)]), compatibility
    )
    assert old["status"] == "fallback_review_required"
    assert "compatible_gpu_headroom_required_for_specialist_precision" in old["blockers"]
    ready = assess_specialist_hardware(
        profile(gpus=[gpu(available=6 * GIB, capability=8.6)]),
        compatibility,
        runtime={"kind": "cuda", "cuda_available": True, "device_indices": [1]},
    )
    assert ready["status"] == "ready"
    assert ready["recommended_accelerator"]["index"] == 1


def test_fp32_can_use_cpu_but_preserves_os_memory_reserve():
    compatibility = {"quantization": "fp32", "max_resident_bytes": 4 * GIB}
    ready = assess_specialist_hardware(profile(memory=8 * GIB), compatibility)
    assert ready["status"] == "ready"
    assert ready["recommended_accelerator"] == {"kind": "cpu"}
    blocked = assess_specialist_hardware(profile(memory=4 * GIB), compatibility)
    assert "insufficient_available_memory_for_specialist" in blocked["blockers"]


def test_fp32_avoids_an_undersized_gpu_and_uses_safe_cpu_fallback():
    compatibility = {"quantization": "fp32", "max_resident_bytes": 5 * GIB}
    ready = assess_specialist_hardware(
        profile(memory=12 * GIB, gpus=[gpu(available=2 * GIB, capability=8.6)]),
        compatibility,
    )
    assert ready["status"] == "ready"
    assert ready["required_available_vram_bytes"] == int(2.5 * GIB)
    assert ready["recommended_accelerator"] == {"kind": "cpu"}


def test_fp32_reports_when_the_installed_runtime_cannot_use_detected_gpu():
    ready = assess_specialist_hardware(
        profile(memory=12 * GIB, gpus=[gpu(available=6 * GIB, capability=8.6)]),
        {"quantization": "fp32", "max_resident_bytes": 5 * GIB},
        runtime={"kind": "cpu", "cuda_available": False, "device_indices": []},
    )
    assert ready["recommended_accelerator"]["index"] == 1
    assert ready["execution_accelerator"] == {"kind": "cpu"}
    assert "cannot use the detected GPU" in ready["runtime_warning"]


def test_half_precision_fails_closed_without_a_usable_cuda_runtime():
    blocked = assess_specialist_hardware(
        profile(memory=12 * GIB, gpus=[gpu(available=6 * GIB, capability=8.6)]),
        {"quantization": "bf16", "max_resident_bytes": 5 * GIB},
        runtime={"kind": "cpu", "cuda_available": False, "device_indices": []},
    )
    assert "compatible_gpu_runtime_unavailable_for_specialist_precision" in blocked["blockers"]


def test_execution_uses_the_runtime_cuda_index_matched_by_uuid():
    selected = gpu(available=6 * GIB, capability=8.6)
    selected["uuid"] = "physical-rtx"
    ready = assess_specialist_hardware(
        profile(memory=12 * GIB, gpus=[selected]),
        {"quantization": "fp32", "max_resident_bytes": 5 * GIB},
        runtime={
            "kind": "cuda",
            "cuda_available": True,
            "device_indices": [0, 1],
            "devices": [{"runtime_index": 0, "uuid": "physical-rtx"}],
        },
    )
    assert ready["execution_accelerator"]["index"] == 0
    assert ready["execution_accelerator"]["physical_index"] == 1
