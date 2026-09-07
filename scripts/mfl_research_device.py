"""Explicit, offline research GPU admission. Does not grant model admission.

Use a full NVIDIA UUID, never a shifting device ordinal. Existing applications
are inspected but never stopped. CPU defaults remain bounded and unchanged.
"""

from __future__ import annotations

from contextlib import contextmanager
import csv
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

GIB = 1024**3
WORKLOAD_MARKERS = (
    "train_mfl", "evaluate_mfl", "diagnose_mfl", "run_mfl_specialist",
    "run_mfl_correction", "run_mfl_practical", "run_mfl_pilot",
    "fast_interchange.worker", "fast_interchange_worker", "mfl_model_worker",
    "llama-server", "llama_server", "ollama runner", "vllm",
    "train_specialist", "train_legal", "specialist_training",
)


def select_gpu(text: str, uuid: str) -> dict:
    if not re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", uuid):
        raise ValueError("explicit full NVIDIA GPU UUID required")
    rows = list(csv.reader(io.StringIO(text)))
    matches = [row for row in rows if row and row[0].strip() == uuid]
    if len(matches) != 1 or len(matches[0]) != 3:
        raise RuntimeError("selected GPU was not uniquely identified")
    row = matches[0]
    try:
        available = int(row[2].strip()) * 1024**2
    except ValueError as exc:
        raise RuntimeError("GPU free memory is unavailable") from exc
    if available < 6 * GIB:
        raise RuntimeError("research GPU requires at least 6 GiB free VRAM")
    return {"uuid": uuid, "name": row[1].strip(), "initial_free_vram_bytes": available}


def workload_conflicts(rows: list[dict], excluded: set[int]) -> list[int]:
    conflicts = []
    for row in rows:
        if row["pid"] in excluded:
            continue
        name = (row.get("name") or "").lower()
        command = " ".join(row.get("cmdline") or []).lower()
        # Uninspectable Python/model workers cannot be assumed idle. System
        # processes unrelated to modeling do not require command-line access.
        if ((not command and any(s in name for s in ("python", "ollama", "llama", "vllm")))
            or any(marker in command or marker in name for marker in WORKLOAD_MARKERS)):
            conflicts.append(row["pid"])
    return sorted(conflicts)


def configure_device(device: str, gpu_uuid: str | None) -> dict:
    if device == "cpu":
        if gpu_uuid:
            raise ValueError("GPU UUID is not allowed for CPU execution")
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        return {"execution_device": "cpu", "precision": "fp32", "cpu_threads": 2}
    if device != "cuda" or not gpu_uuid:
        raise ValueError("CUDA research requires an explicit GPU UUID")
    if "torch" in sys.modules:
        raise RuntimeError("GPU selection must precede Torch import")
    import psutil

    process = psutil.Process()
    excluded = {process.pid, *(p.pid for p in process.parents())}
    rows = [p.info for p in psutil.process_iter(["pid", "name", "cmdline"], ad_value=None)]
    conflicts = workload_conflicts(rows, excluded)
    if conflicts:
        raise RuntimeError(f"another or uninspectable model workload is active: PIDs {conflicts}")
    if psutil.virtual_memory().available < 8 * GIB:
        raise RuntimeError("research GPU requires 8 GiB available system RAM")
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise RuntimeError("NVIDIA inventory tool unavailable")
    result = subprocess.run(
        [executable, "--query-gpu=uuid,name,memory.free", "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True, timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    selected = select_gpu(result.stdout, gpu_uuid)
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_uuid
    if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    return {"execution_device": "cuda:0", "precision": "bf16", "cpu_threads": 2,
            "policy": "exclusive_uuid_gpu_research_only", "gpu": selected,
            "initial_system_memory_floor_bytes": 8 * GIB,
            "remaining_system_memory_floor_bytes": 4 * GIB,
            "remaining_free_vram_floor_bytes": GIB,
            "other_processes_changed": False}


def validate_torch_device(torch, resources: dict) -> None:
    if resources["execution_device"] == "cpu":
        return
    if (not torch.cuda.is_available() or torch.cuda.device_count() != 1
        or not torch.cuda.is_bf16_supported(including_emulation=False)):
        raise RuntimeError("selected GPU must provide native BF16 CUDA support")
    properties = torch.cuda.get_device_properties(0)
    actual_uuid = str(getattr(properties, "uuid", ""))
    # PyTorch's _CUuuid omits nvidia-smi's literal GPU- prefix. Compare the
    # complete UUID; do not accept prefixes, names or device ordinals.
    if actual_uuid.removeprefix("GPU-").lower() != resources["gpu"]["uuid"].removeprefix("GPU-").lower():
        raise RuntimeError("CUDA device identity differs from selected UUID")
    torch.cuda.reset_peak_memory_stats()


def check_gpu_headroom(torch, resources: dict) -> None:
    if resources["execution_device"] == "cpu":
        return
    import psutil
    if psutil.virtual_memory().available < resources["remaining_system_memory_floor_bytes"]:
        raise RuntimeError("GPU research stopped to preserve system memory")
    if torch.cuda.mem_get_info()[0] < resources["remaining_free_vram_floor_bytes"]:
        raise RuntimeError("GPU research stopped to preserve VRAM headroom")


def record_start_failure(output: Path, exc: Exception, *, training: bool) -> dict:
    """Retain startup failures too; never overwrite a previous run's receipt."""
    from scripts.train_mfl_adapter_continuation import ROOT, write_json
    root = (ROOT / "dist").resolve()
    if (any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
            for p in (output, *output.parents))
        or output.resolve() == root or not output.resolve().is_relative_to(root)):
        raise ValueError("failure receipt must stay in repository dist") from exc
    receipt = output / "training-run.json" if training else output
    if receipt.exists():
        raise ValueError("preserve the previous research receipt") from exc
    report = {"schema": "mfl.research-start-failure.v1", "status": "blocked_before_generation_or_training",
              "error_type": type(exc).__name__, "error": str(exc),
              "production_admitted": False, "quality_qualified": False,
              "models_loaded": False, "training": training}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt, report)
    return report


@contextmanager
def research_lock():
    """One participating research process, auto-released even after interruption."""
    from scripts.train_mfl_adapter_continuation import ROOT
    if os.name != "nt":
        raise RuntimeError("research workload lock is qualified only on Windows")
    import msvcrt
    path = ROOT / "dist/model-candidates/research-workload.lock"
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
           for p in (path, *path.parents)):
        raise ValueError("linked research lock forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("another repository research operation holds the lock") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
