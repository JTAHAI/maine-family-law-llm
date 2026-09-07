"""Model-specific local hardware admission before an inference worker starts."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

GIB = 1024**3


@lru_cache(maxsize=1)
def installed_torch_runtime() -> dict[str, Any]:
    """Report what the installed inference runtime can actually execute.

    A driver inventory can see a GPU while the desktop application carries a
    CPU-only Torch build (or CUDA is masked for this process).  Reporting that
    GPU as usable leaves a person watching a misleading long-running spinner.
    This probes no model, sends no data, and changes no device state.
    """

    try:
        import torch
    except Exception:
        return {
            "schema_version": "fast_interchange_runtime_capability_v1",
            "kind": "unavailable",
            "cuda_available": False,
            "device_indices": [],
            "reason": "torch_runtime_unavailable",
        }
    try:
        cuda_available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if cuda_available else 0
        devices = []
        for index in range(max(0, min(device_count, 32))):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "runtime_index": index,
                    "uuid": str(getattr(properties, "uuid", "")).replace("GPU-", "").casefold(),
                    "name": str(getattr(properties, "name", ""))[:160],
                }
            )
    except Exception:
        cuda_available, device_count, devices = False, 0, []
    return {
        "schema_version": "fast_interchange_runtime_capability_v1",
        "kind": "cuda" if cuda_available else "cpu",
        "cuda_available": cuda_available,
        "device_indices": list(range(max(0, min(device_count, 32)))),
        "devices": devices,
        "reason": "cuda_available" if cuda_available else "cuda_runtime_unavailable",
    }


def assess_specialist_hardware(
    profile: dict[str, Any], compatibility: dict[str, Any], *, runtime: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return a public, content-free readiness decision for one signed release."""

    quantization = str(compatibility.get("quantization") or "").strip().casefold()
    resident = max(0, int(compatibility.get("max_resident_bytes") or 0))
    available_memory = max(0, int(profile.get("available_memory_bytes") or 0))
    gpus = [row for row in (profile.get("details") or {}).get("gpus", []) if isinstance(row, dict)]
    blockers: list[str] = []
    if not resident:
        blockers.append("specialist_resident_memory_requirement_missing")
    elif available_memory < resident + GIB:
        blockers.append("insufficient_available_memory_for_specialist")

    minimum_compute = 8.0 if quantization == "bf16" else 6.0
    required_vram = (
        max(2 * GIB, min(4 * GIB, resident // 2))
        if quantization in {"fp32", "bf16", "fp16"}
        else 0
    )
    compatible = [
        row
        for row in gpus
        if float(row.get("compute_capability") or 0) >= minimum_compute
        and int(row.get("available_vram_bytes") or 0) >= required_vram
    ]
    if quantization in {"bf16", "fp16"} and not compatible:
        blockers.append("compatible_gpu_headroom_required_for_specialist_precision")
    if quantization not in {"fp32", "fp16", "bf16"}:
        blockers.append("specialist_precision_requirement_invalid")

    selected = max(
        compatible,
        key=lambda row: (
            int(row.get("available_vram_bytes") or 0),
            float(row.get("compute_capability") or 0),
        ),
        default=None,
    )
    runtime = dict(runtime or installed_torch_runtime())
    runtime_indices = {
        index
        for index in runtime.get("device_indices", [])
        if isinstance(index, int) and 0 <= index <= 31
    }
    runtime_device = None
    if selected and runtime.get("cuda_available") is True:
        selected_uuid = str(selected.get("uuid") or "").replace("GPU-", "").casefold()
        runtime_devices = [row for row in runtime.get("devices", []) if isinstance(row, dict)]
        runtime_device = next(
            (
                row
                for row in runtime_devices
                if selected_uuid
                and str(row.get("uuid") or "").replace("GPU-", "").casefold()
                == selected_uuid
            ),
            None,
        )
        # Synthetic profiles and older runtimes may not expose UUIDs.  The
        # direct-index fallback remains only for that compatibility case.
        if (
            runtime_device is None
            and not runtime_devices
            and int(selected.get("index") or -1) in runtime_indices
        ):
            runtime_device = {"runtime_index": int(selected.get("index") or 0)}
    runtime_can_use_selected = runtime_device is not None
    if quantization in {"bf16", "fp16"} and compatible and not runtime_can_use_selected:
        blockers.append("compatible_gpu_runtime_unavailable_for_specialist_precision")
    if runtime_can_use_selected:
        execution_accelerator: dict[str, Any] = {
            "index": int(runtime_device.get("runtime_index") or 0),
            "physical_index": selected.get("index"),
            "name": str(selected.get("name") or "")[:160],
            "available_vram_bytes": int(selected.get("available_vram_bytes") or 0),
            "compute_capability": float(selected.get("compute_capability") or 0),
        }
        runtime_warning = ""
    else:
        execution_accelerator = {"kind": "cpu"}
        runtime_warning = (
            "The installed local model runtime cannot use the detected GPU; "
            "this FP32 specialist will use CPU fallback and may take longer."
            if selected and quantization == "fp32"
            else ""
        )
    return {
        "schema_version": "fast_interchange_hardware_readiness_v1",
        "status": "ready" if not blockers else "fallback_review_required",
        "blockers": blockers,
        "available_memory_bytes": available_memory,
        "required_resident_memory_bytes": resident,
        "required_available_vram_bytes": required_vram,
        "quantization": quantization or "unknown",
        "recommended_accelerator": (
            {
                "index": selected.get("index"),
                "name": str(selected.get("name") or "")[:160],
                "available_vram_bytes": int(selected.get("available_vram_bytes") or 0),
                "compute_capability": float(selected.get("compute_capability") or 0),
            }
            if selected
            else {"kind": "cpu"}
            if quantization == "fp32" and not blockers
            else None
        ),
        "execution_accelerator": execution_accelerator,
        "runtime_capability": runtime,
        "runtime_warning": runtime_warning,
        "fallback": "deterministic_host_with_human_review",
        "network_used": False,
        "review_required": True,
    }
