from __future__ import annotations

import ctypes
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _total_memory_bytes() -> int:
    if hasattr(os, "sysconf"):
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_PHYS_PAGES" in names:
            try:
                return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
            except (OSError, ValueError, TypeError):
                pass
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullTotalPhys)
    return 0


def _available_memory_bytes() -> int:
    if hasattr(os, "sysconf"):
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_AVPHYS_PAGES" in names:
            try:
                return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES"))
            except (OSError, ValueError, TypeError):
                pass
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullAvailPhys)
    return 0


def _gpu_hint() -> str:
    for name in ("NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "ROCM_VISIBLE_DEVICES"):
        value = os.environ.get(name, "").strip()
        if value and value not in {"void", "none", "-1"}:
            return value
    return ""


def _instruction_sets() -> tuple[str, ...]:
    hints: list[str] = []
    processor = (platform.processor() or "").lower()
    if "x86" in processor or "amd64" in processor or "intel" in processor or "ryzen" in processor:
        hints.extend(["sse2", "sse4.2"])
    if "avx2" in processor:
        hints.append("avx2")
    if os.environ.get("MFL_FORCE_AVX512", "").strip() == "1":
        hints.append("avx512")
    return tuple(sorted(set(hints)))


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    os_version: str
    machine: str
    architecture: str
    logical_cpu_count: int
    total_memory_bytes: int
    available_memory_bytes: int
    disk_free_bytes: int
    gpu_hint: str = ""
    gpu_name: str = ""
    vram_bytes: int = 0
    current_operating_mode: str = "local_only"
    instruction_sets: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_concurrency: int = 1
    recommended_context_limit: int = 0
    estimated_peak_memory_bytes: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "machine": self.machine,
            "architecture": self.architecture,
            "logical_cpu_count": self.logical_cpu_count,
            "total_memory_bytes": self.total_memory_bytes,
            "available_memory_bytes": self.available_memory_bytes,
            "disk_free_bytes": self.disk_free_bytes,
            "gpu_hint": self.gpu_hint,
            "gpu_name": self.gpu_name,
            "vram_bytes": self.vram_bytes,
            "current_operating_mode": self.current_operating_mode,
            "instruction_sets": list(self.instruction_sets),
            "warnings": list(self.warnings),
            "recommended_concurrency": self.recommended_concurrency,
            "recommended_context_limit": self.recommended_context_limit,
            "estimated_peak_memory_bytes": self.estimated_peak_memory_bytes,
            "details": dict(self.details),
        }


def profile_hardware(root: str | Path) -> HardwareProfile:
    root_path = Path(root)
    disk_free = 0
    try:
        disk_free = int(shutil.disk_usage(root_path).free)
    except FileNotFoundError:
        parent = root_path.parent if root_path.parent != root_path else Path.home()
        try:
            disk_free = int(shutil.disk_usage(parent).free)
        except Exception:
            disk_free = 0

    total_memory = _total_memory_bytes()
    available_memory = _available_memory_bytes() or total_memory
    cpu_count = os.cpu_count() or 1
    instruction_sets = _instruction_sets()
    warnings: list[str] = []
    if available_memory and available_memory < 4 * 1024**3:
        warnings.append("low_available_memory")
    if disk_free and disk_free < 10 * 1024**3:
        warnings.append("low_disk_space")
    gpu_hint = _gpu_hint()
    if not gpu_hint:
        warnings.append("no_gpu_hint_detected")

    recommended_concurrency = 1 if available_memory and available_memory < 8 * 1024**3 else max(1, min(4, cpu_count // 2 or 1))
    recommended_context_limit = 4096 if available_memory and available_memory < 8 * 1024**3 else 8192
    estimated_peak_memory_bytes = max(0, min(total_memory or available_memory, int(available_memory * 0.65))) if available_memory else 0

    return HardwareProfile(
        os_name=platform.system() or "unknown",
        os_version=platform.version() or "unknown",
        machine=platform.machine() or "unknown",
        architecture=platform.architecture()[0] if platform.architecture() else "unknown",
        logical_cpu_count=cpu_count,
        total_memory_bytes=total_memory,
        available_memory_bytes=available_memory,
        disk_free_bytes=disk_free,
        gpu_hint=gpu_hint,
        gpu_name=os.environ.get("MFL_GPU_NAME", "").strip(),
        vram_bytes=int(os.environ.get("MFL_VRAM_BYTES", "0") or 0),
        current_operating_mode="local_only",
        instruction_sets=instruction_sets,
        warnings=tuple(sorted(set(warnings))),
        recommended_concurrency=recommended_concurrency,
        recommended_context_limit=recommended_context_limit,
        estimated_peak_memory_bytes=estimated_peak_memory_bytes,
        details={
            "platform": platform.platform(),
            "processor": platform.processor() or "",
            "python": platform.python_version(),
        },
    )
