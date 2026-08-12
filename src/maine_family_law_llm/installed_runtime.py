"""Helpers for resolving and launching the installed Windows package."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .version import APP_EXECUTABLE_NAME

DEFAULT_PACKAGE_NAME = "TAHAIWebServices.MaineFamilyLawLLM"


@dataclass(frozen=True)
class InstalledRuntimeResolution:
    package_name: str
    package_full_name: str
    install_location: str
    version: str
    executable_path: str
    source: str
    available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fallback_runtime_executable(fallback_runtime_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    env_root = str(os.environ.get("MFL_RUNTIME_ROOT") or "").strip()
    if env_root:
        candidates.append(Path(env_root))
    if fallback_runtime_root is not None:
        candidates.append(Path(fallback_runtime_root))
    repo_runtime = Path(__file__).resolve().parents[2] / "dist" / "store" / "runtime"
    candidates.append(repo_runtime)
    for root in candidates:
        exe = root / APP_EXECUTABLE_NAME
        if exe.is_file():
            return exe
    return None


def resolve_installed_runtime_executable(
    package_name: str = DEFAULT_PACKAGE_NAME,
    *,
    fallback_runtime_root: Path | None = None,
) -> InstalledRuntimeResolution:
    """Resolve the installed Store package executable, or fall back to the bundled runtime."""

    command = (
        f"$pkg = Get-AppxPackage -Name '{package_name}' -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 PackageFullName,InstallLocation,Version; "
        "if ($pkg) { $pkg | ConvertTo-Json -Compress }"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        completed = None

    if completed and completed.returncode == 0 and completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            install_location = str(payload.get("InstallLocation") or "").strip()
            package_full_name = str(payload.get("PackageFullName") or "").strip()
            version = str(payload.get("Version") or "").strip()
            if install_location:
                exe = Path(install_location) / APP_EXECUTABLE_NAME
                if exe.is_file():
                    return InstalledRuntimeResolution(
                        package_name=package_name,
                        package_full_name=package_full_name,
                        install_location=install_location,
                        version=version,
                        executable_path=str(exe),
                        source="appx_package",
                        available=True,
                    )

    fallback_exe = _fallback_runtime_executable(fallback_runtime_root)
    if fallback_exe is not None:
        return InstalledRuntimeResolution(
            package_name=package_name,
            package_full_name="",
            install_location=str(fallback_exe.parent),
            version="",
            executable_path=str(fallback_exe),
            source="bundled_runtime",
            available=False,
        )

    return InstalledRuntimeResolution(
        package_name=package_name,
        package_full_name="",
        install_location="",
        version="",
        executable_path="",
        source="unresolved",
        available=False,
    )
