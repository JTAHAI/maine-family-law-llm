"""Audit one MSIX for the FAST INTERCHANGE adapter-runtime contract.

This checks that the exact sealed package contains the importable runtime
dependencies required to load an externally admitted local LoRA adapter. It
does not assert that a legal model, adapter, admission, or quality evaluation
exists; those artifacts intentionally remain outside the package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_IMPORT_FILES = {
    "peft": "_internal/peft/__init__.py",
    "accelerate": "_internal/accelerate/__init__.py",
    "safetensors": "_internal/safetensors/__init__.py",
}
REQUIRED_NATIVE_FILES = {"safetensors": "_internal/safetensors/_safetensors_rust.pyd"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_package(package: Path) -> dict[str, Any]:
    """Return a deterministic package-content result without extracting it."""

    if not package.is_file() or package.suffix.casefold() != ".msix":
        raise ValueError("package must be an existing .msix file")
    with zipfile.ZipFile(package) as archive:
        entries = {entry.filename for entry in archive.infolist()}

    packages: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for package_name, import_path in REQUIRED_IMPORT_FILES.items():
        metadata = any(
            entry.startswith(f"_internal/{package_name}-")
            and entry.endswith(".dist-info/METADATA")
            for entry in entries
        )
        native_path = REQUIRED_NATIVE_FILES.get(package_name)
        importable = import_path in entries
        native = native_path in entries if native_path else True
        package_missing = [
            item
            for item, present in (
                (import_path, importable),
                (f"{package_name} distribution metadata", metadata),
                (native_path, native),
            )
            if item and not present
        ]
        packages[package_name] = {
            "import_path": import_path,
            "importable": importable,
            "distribution_metadata": metadata,
            "native_extension": native_path,
            "native_extension_present": native,
            "missing": package_missing,
        }
        missing.extend(package_missing)

    return {
        "schema_version": "fast_interchange_package_runtime_v1",
        "package": str(package),
        "package_sha256": _sha256(package),
        "package_entry_count": len(entries),
        "packages": packages,
        "missing": missing,
        "status": "pass_runtime_dependencies_present" if not missing else "fail_runtime_dependencies_missing",
        "evidence_level": "exact_msix_archive_dependency_presence",
        "limitations": [
            "Does not run model inference.",
            "Does not provide legal weights, adapters, a trusted release registry, or an admission grant.",
            "Does not establish legal quality, frozen-app end-to-end inference, Store readiness, or Enterprise readiness.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_package(args.package.resolve())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {
            "schema_version": "fast_interchange_package_runtime_v1",
            "package": str(args.package),
            "status": "fail_runtime_audit_error",
            "error": type(exc).__name__,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "pass_runtime_dependencies_present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
