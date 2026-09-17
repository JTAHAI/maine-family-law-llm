"""Read-only installed dependency/notice inventory; never a production admission.

This audits installed RECORDs and a conservative Python-runtime selection. It
does not download wheels, copy environments, import models, certify publisher
provenance, prove dynamic import closure, or replace a final-package audit.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import sys
import time
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
SEEDS = (
    "torch",
    "transformers",
    "safetensors",
    "tokenizers",
    "numpy",
    "psutil",
    "requests",
    "cryptography",
    "pydantic",
)
CAP = 1_500_000_000
CACHE_SUFFIXES = {".pyc", ".pyo"}


def safe_name(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", value) is None
    ):
        raise ValueError("invalid_package_identity")
    return canonicalize_name(value)


def dependency_closure(seeds, lookup=metadata.distribution, environment=None):
    """Evaluate target-platform markers and requested transitive extras exactly."""
    environment = dict(default_environment() if environment is None else environment)
    pending = deque((safe_name(name), frozenset()) for name in seeds)
    visited, packages, edges, blockers = set(), {}, [], []
    while pending:
        name, extras = pending.popleft()
        key = (name, extras)
        if key in visited:
            continue
        visited.add(key)
        try:
            dist = lookup(name)
        except metadata.PackageNotFoundError:
            blockers.append({"code": "required_distribution_missing", "package": name})
            continue
        try:
            actual_name = safe_name(dist.metadata.get("Name", ""))
        except ValueError:
            blockers.append({"code": "invalid_distribution_identity", "package": name})
            continue
        if name != actual_name:
            blockers.append({"code": "distribution_identity_mismatch", "package": name})
            continue
        packages[name] = dist
        for raw in dist.requires or ():
            try:
                requirement = Requirement(raw)
            except InvalidRequirement:
                blockers.append({"code": "invalid_dependency_metadata", "package": name})
                continue
            dependency = safe_name(requirement.name)
            if requirement.marker and not any(
                requirement.marker.evaluate({**environment, "extra": extra})
                for extra in ({""} | set(extras))
            ):
                continue
            edge = {
                "package": name,
                "dependency": dependency,
                "specifier": str(requirement.specifier),
                "extras": sorted(requirement.extras),
            }
            if edge not in edges:
                edges.append(edge)
            if requirement.url:
                # Never print possibly credential-bearing URLs from local metadata.
                blockers.append(
                    {
                        "code": "direct_url_dependency_requires_review",
                        "package": name,
                        "dependency": dependency,
                    }
                )
                continue
            try:
                installed = lookup(dependency)
                if installed.version not in requirement.specifier:
                    blockers.append(
                        {
                            "code": "dependency_version_mismatch",
                            "package": name,
                            "dependency": dependency,
                            "installed": installed.version,
                            "required": str(requirement.specifier),
                        }
                    )
            except metadata.PackageNotFoundError:
                blockers.append({"code": "required_distribution_missing", "package": dependency})
                continue
            pending.append((dependency, frozenset(requirement.extras)))
    return packages, edges, blockers


def logical_path(candidate: Path, roots: dict[str, Path]):
    resolved = candidate.resolve(strict=True)
    for label, root in sorted(roots.items(), key=lambda row: len(str(row[1])), reverse=True):
        anchor = root.resolve(strict=True)
        if resolved.is_relative_to(anchor):
            if not resolved.is_file() or candidate.is_symlink():
                raise ValueError("runtime_file_not_regular")
            return f"{label}/{resolved.relative_to(anchor).as_posix()}", resolved
    raise ValueError("runtime_file_outside_approved_roots")


def file_record(candidate, roots, *, expected_hash=None, expected_size=None):
    label, resolved = logical_path(Path(candidate), roots)
    algorithms = {"sha256"}
    if expected_hash:
        if expected_hash.mode not in {"sha256", "sha384", "sha512"}:
            raise ValueError("unsupported_record_hash_algorithm")
        algorithms.add(expected_hash.mode)
    digests = {name: hashlib.new(name) for name in algorithms}
    with resolved.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not 0 <= before.st_size < CAP:
            raise ValueError("runtime_file_size_budget_exceeded")
        if expected_size is not None and before.st_size != expected_size:
            raise ValueError("installed_record_size_mismatch")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(chunk)
        after = os.fstat(stream.fileno())
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("runtime_file_changed_during_hash")
    if expected_size is not None and before.st_size != expected_size:
        raise ValueError("installed_record_size_mismatch")
    if expected_hash:
        encoded = (
            base64.urlsafe_b64encode(digests[expected_hash.mode].digest()).decode().rstrip("=")
        )
        if encoded != expected_hash.value:
            raise ValueError("installed_record_hash_mismatch")
    return {
        "path": label,
        "bytes": before.st_size,
        "sha256": digests["sha256"].hexdigest(),
        "installed_record_hash_checked": expected_hash is not None,
    }


def license_paths(dist, names):
    """Resolve declared wheel license locations without reading arbitrary URLs."""
    info = next(
        (Path(name).parent.as_posix() for name in names if name.endswith(".dist-info/METADATA")),
        None,
    )
    notices = sorted(
        name
        for name in names
        if re.match(r"(?i)^(license|licence|copying|notice|copyright)([._-].*)?$", Path(name).name)
    )
    missing = []
    for declared in dist.metadata.get_all("License-File") or ():
        relative = Path(declared.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or not info:
            missing.append("unsafe_declared_license_path")
            continue
        choices = {f"{info}/licenses/{relative.as_posix()}", f"{info}/{relative.as_posix()}"}
        present = choices.intersection(names)
        if not present:
            missing.append(relative.as_posix())
        notices.extend(present)
    return sorted(set(notices)), missing


def python_runtime_files(base: Path):
    """Conservative stdlib/DLL footprint, excluding caches and installed packages.

    Includes stdlib tests/idle/tkinter if present instead of quietly assuming
    they can all be stripped. It is a selection proposal, not a shipped layout.
    """
    selected = [
        p
        for p in base.iterdir()
        if p.is_file() and (p.suffix.lower() in {".exe", ".dll"} or p.name == "LICENSE.txt")
    ]
    excluded = {"site-packages", "__pycache__"}
    for name in ("Lib", "DLLs", "tcl"):
        directory = base / name
        if not directory.is_dir():
            continue
        for parent, directories, files in os.walk(directory, followlinks=False):
            directories[:] = [
                d for d in directories if d not in excluded and not (Path(parent) / d).is_symlink()
            ]
            for filename in files:
                path = Path(parent) / filename
                if path.suffix.lower() not in CACHE_SUFFIXES:
                    selected.append(path)
    return selected


def model_inventory(directory: Path):
    """Recheck the existing pinned six-file receipt; never accept new paths."""
    receipt_bytes = (directory / "acquisition.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    expected_names = {
        "README.md",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "model.safetensors",
        "config_sentence_transformers.json",
    }
    entries = receipt["files"]
    if len(entries) != len(expected_names) or {item["path"] for item in entries} != expected_names:
        raise ValueError("model_receipt_selection_mismatch")
    files = []
    for entry in entries:
        item = file_record(
            directory / entry["path"], {"ranker_model": directory}, expected_size=entry["bytes"]
        )
        if item["sha256"] != entry["sha256"]:
            raise ValueError("model_receipt_hash_mismatch")
        files.append(item)
    return {
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "files": files,
        "bytes": sum(item["bytes"] for item in files),
    }


def runtime_roots(package_runtime=None):
    package_root = Path(sys.prefix if package_runtime is None else package_runtime).resolve(
        strict=True
    )
    if (
        not (package_root / "pyvenv.cfg").is_file()
        or not (package_root / "Scripts/python.exe").is_file()
        or not (package_root / "Lib/site-packages").is_dir()
    ):
        raise ValueError("package_runtime_must_be_explicit_windows_venv")
    return {
        "package_runtime": package_root,
        "python_runtime": Path(sys.base_prefix).resolve(strict=True),
    }


def execute(run_id, package_runtime=None, *, include_tokenizers_notice=False):
    if re.fullmatch(r"[a-z0-9-]{1,24}", run_id) is None:
        raise ValueError("invalid_audit_id")
    report_path = OUTPUT / f"ranker-runtime-audit-{run_id}.json"
    inventory_path = OUTPUT / f"ranker-runtime-files-{run_id}.jsonl"
    if report_path.exists() or inventory_path.exists():
        raise ValueError("preserve_prior_evidence")
    started = time.monotonic()
    roots = runtime_roots(package_runtime)
    packages, edges, blockers = dependency_closure(SEEDS)
    report = {
        "schema_version": "compact_ranker_installed_runtime_audit_v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "package_runtime_selection": "explicit_existing_venv"
        if package_runtime
        else "interpreter_prefix",
        "package_runtime_config_sha256": hashlib.sha256(
            (roots["package_runtime"] / "pyvenv.cfg").read_bytes()
        ).hexdigest(),
        "target": {
            key: default_environment()[key]
            for key in ("python_full_version", "platform_system", "platform_machine")
        },
        "seed_packages": list(SEEDS),
        "dependency_edges": edges,
        "packages": [],
        "supplemental_notices_requested": include_tokenizers_notice,
        "inventory_file": inventory_path.name,
        "blockers": blockers,
        "notes": [
            "Declared dependency closure is not observed dynamic-import closure.",
            "Installed RECORD matching is consistency, not publisher authentication.",
            "File hashes are a measured inventory, not an immutable locked serving snapshot.",
            "No model or runtime was copied, downloaded or loaded for inference.",
            "OS-provided native dependencies and final frozen layout are not qualified here.",
            "Notice presence is not a legal license-compliance determination.",
            "Untracked files in installed packages are not included or approved for copying.",
        ],
        "complete_runtime_qualified": False,
        "production_admitted": False,
        "ga_ready": False,
    }
    seen, package_bytes = set(), 0
    installed_notices_complete = True
    with inventory_path.open("x", encoding="utf-8") as inventory:
        for name, dist in sorted(packages.items()):
            entries = tuple(dist.files or ())
            names = {str(entry).replace("\\", "/") for entry in entries}
            notices, missing_notices = license_paths(dist, names)
            row = {
                "name": name,
                "version": dist.version,
                "bytes": 0,
                "files": 0,
                "record_hashes_checked": 0,
                "unhashed_record_entries": 0,
                "cache_entries_excluded": 0,
                "notice_files": [],
                "missing_declared_notices": missing_notices,
                "license_expression": (dist.metadata.get("License-Expression") or "")[:512],
                "license_classifier": [
                    v
                    for v in dist.metadata.get_all("Classifier") or []
                    if v.startswith("License ::")
                ],
                "license_review": "not_cleared",
            }
            if not entries:
                blockers.append({"code": "distribution_record_missing", "package": name})
            notice_available = bool(notices) and not missing_notices
            installed_notices_complete &= notice_available
            if name == "tokenizers" and include_tokenizers_notice:
                from scripts.qualify_compact_tokenizers_notice import (
                    DIRECTORY,
                    LICENSE,
                    inspect_installed,
                )

                try:
                    proof = inspect_installed(dist, DIRECTORY)
                    item = file_record(
                        DIRECTORY / LICENSE["name"], {"supplemental_notices": DIRECTORY}
                    )
                    if item["sha256"] != proof["artifacts"][1]["sha256"]:
                        raise ValueError("supplemental_notice_changed")
                    row["supplemental_notice_proof"] = proof
                    row["notice_files"].append(item)
                    seen.add(item["path"].casefold())
                    package_bytes += item["bytes"]
                    inventory.write(
                        json.dumps({**item, "package": name}, separators=(",", ":")) + "\n"
                    )
                    # Do not mask a missing explicitly declared license file.
                    notice_available = not missing_notices
                except (OSError, ValueError, KeyError, TypeError):
                    blockers.append(
                        {"code": "supplemental_notice_verification_failed", "package": name}
                    )
            if not notice_available:
                blockers.append({"code": "license_notice_inventory_incomplete", "package": name})
            for entry in entries:
                if Path(entry).suffix.lower() in CACHE_SUFFIXES:
                    row["cache_entries_excluded"] += 1
                    continue
                try:
                    item = file_record(
                        dist.locate_file(entry),
                        roots,
                        expected_hash=entry.hash,
                        expected_size=entry.size,
                    )
                except (ValueError, OSError) as exc:
                    blockers.append(
                        {
                            "code": str(exc)
                            if isinstance(exc, ValueError)
                            else "runtime_file_unreadable",
                            "package": name,
                            "entry_sha256": hashlib.sha256(str(entry).encode()).hexdigest(),
                        }
                    )
                    continue
                row["files"] += 1
                row["bytes"] += item["bytes"]
                row["record_hashes_checked"] += bool(entry.hash)
                row["unhashed_record_entries"] += not bool(entry.hash)
                if str(entry).replace("\\", "/") in notices:
                    row["notice_files"].append(item)
                if item["path"].casefold() not in seen:
                    seen.add(item["path"].casefold())
                    package_bytes += item["bytes"]
                    inventory.write(
                        json.dumps({**item, "package": name}, separators=(",", ":")) + "\n"
                    )
            report["packages"].append(row)
            print(
                json.dumps({"package": name, "bytes": row["bytes"], "files": row["files"]}),
                flush=True,
            )
        python_bytes, python_count = 0, 0
        for candidate in python_runtime_files(roots["python_runtime"]):
            try:
                item = file_record(candidate, roots)
            except (OSError, ValueError):
                blockers.append({"code": "python_runtime_file_unreadable"})
                continue
            if item["path"].casefold() not in seen:
                seen.add(item["path"].casefold())
                python_bytes += item["bytes"]
                python_count += 1
                inventory.write(
                    json.dumps({**item, "package": "cpython-runtime"}, separators=(",", ":")) + "\n"
                )
    try:
        model = model_inventory(OUTPUT / "legal-passage-reranker")
    except (OSError, ValueError, KeyError, TypeError):
        model = {"bytes": 0, "files": []}
        blockers.append({"code": "model_receipt_integrity_failed"})
    model_bytes = model["bytes"]
    report["model_inventory"] = model
    integrity_passed = not any(b["code"] != "license_notice_inventory_incomplete" for b in blockers)
    report.update(
        package_files=len(seen) - python_count,
        package_bytes=package_bytes,
        python_runtime_files=python_count,
        python_runtime_bytes=python_bytes,
        model_selected_bytes=model_bytes,
        measured_selection_bytes=package_bytes + python_bytes + model_bytes,
        measured_selection_under_cap=(
            integrity_passed and package_bytes + python_bytes + model_bytes < CAP
        ),
        cap_bytes=CAP,
        installed_selection_integrity_passed=integrity_passed,
        installed_notice_inventory_complete=installed_notices_complete,
        notice_inventory_complete=not any(
            b["code"] == "license_notice_inventory_incomplete" for b in blockers
        ),
        inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        distribution_count=len(packages),
        duration_seconds=round(time.monotonic() - started, 3),
        decision="BLOCKED_RUNTIME_QUALIFICATION",
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "distribution_count",
                    "package_bytes",
                    "python_runtime_bytes",
                    "model_selected_bytes",
                    "measured_selection_bytes",
                    "measured_selection_under_cap",
                    "duration_seconds",
                )
            }
            | {"blocker_counts": dict(Counter(item["code"] for item in blockers))}
        ),
        flush=True,
    )
    return not blockers


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--package-runtime",
        type=Path,
        help="Explicit existing Windows venv; read-only, never copied",
    )
    parser.add_argument(
        "--include-tokenizers-notice",
        action="store_true",
        help="Read-only recheck of the separately acquired pinned Tokenizers notice and wheel",
    )
    args = parser.parse_args()
    raise SystemExit(
        0
        if execute(
            args.run_id,
            args.package_runtime,
            include_tokenizers_notice=args.include_tokenizers_notice,
        )
        else 1
    )
