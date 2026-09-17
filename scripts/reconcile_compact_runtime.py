"""Targeted installed RECORD/notice audit, not publisher or runtime admission."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import sys
import time
from email.parser import Parser
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
sys.path.insert(0, str(ROOT))
from legal.fast_interchange.compact_ranker_process import selected_runtime_site  # noqa: E402
from legal.fast_interchange.compact_span_reader import PINNED  # noqa: E402
from legal.security.durable_io import read_bounded_regular_file  # noqa: E402
from legal.security.strict_json import strict_json_load_path  # noqa: E402
from scripts.audit_compact_ranker_runtime import file_record, license_paths  # noqa: E402


def safe_relative(name):
    path = PurePosixPath(name)
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }
    return (
        bool(name)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and ":" not in name
        and not any(ord(character) < 32 or character in '<>"?*|' for character in name)
        and all(
            part not in {"", ".", ".."}
            and part == part.strip()
            and not part.endswith(".")
            and part.split(".")[0].upper() not in reserved
            for part in name.split("/")
        )
    )


def parse_record(raw):
    rows = {}
    for row in csv.reader(io.StringIO(raw.decode("utf-8"))):
        if len(row) != 3:
            raise ValueError("record_row_invalid")
        name, checksum, size = row
        if not safe_relative(name):
            continue  # External entry is not a candidate and is never dereferenced.
        key = name.casefold()
        if key in rows:
            raise ValueError("record_duplicate_path")
        expected = None
        if checksum:
            algorithm, separator, value = checksum.partition("=")
            if not separator or algorithm not in {"sha256", "sha384", "sha512"}:
                raise ValueError("record_hash_invalid")
            decoded = base64.b64decode(
                value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
            )
            if len(decoded) != hashlib.new(algorithm).digest_size:
                raise ValueError("record_hash_invalid")
            expected = SimpleNamespace(mode=algorithm, value=value.rstrip("="))
        size_value = None
        if size:
            if not size.isascii() or not size.isdecimal() or int(size) >= 1_500_000_000:
                raise ValueError("record_size_invalid")
            size_value = int(size)
        rows[key] = dict(path=name, hash=expected, size=size_value)
    return rows


def public_origin(metadata):
    origins = []
    for value in metadata.get_all("Project-URL", []) + metadata.get_all("Home-page", []):
        url = value.split(",", 1)[-1].strip()
        parsed = urlsplit(url)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
        ):
            origins.append(url)
    return sorted(set(origins))[:10]


def build_ownership(site, wanted):
    owners, packages, errors = {}, {}, []
    for info in sorted(site.glob("*.dist-info")):
        try:
            if info.is_symlink() or getattr(info.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError("metadata_link_forbidden")
            raw = read_bounded_regular_file(info / "RECORD", max_bytes=16_000_000)
            rows = parse_record(raw)
            relevant = wanted & rows.keys()
            if not relevant:
                continue
            metadata_raw = read_bounded_regular_file(info / "METADATA", max_bytes=2_000_000)
            metadata = Parser().parsestr(metadata_raw.decode("utf-8"))
            name, version = metadata.get("Name", ""), metadata.get("Version", "")
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) is None or len(version) > 100:
                raise ValueError("package_identity_invalid")
            key = info.name
            notices, missing = license_paths(
                SimpleNamespace(metadata=metadata), {r["path"] for r in rows.values()}
            )
            packages[key] = dict(
                name=name,
                version=version,
                record_sha256=hashlib.sha256(raw).hexdigest(),
                metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
                license_expression=metadata.get("License-Expression", "")[:512],
                license_summary=metadata.get("License", "")[:512],
                declared_origins=public_origin(metadata),
                origin_verified=False,
                license_review="not_cleared",
                notice_paths=notices,
                missing_declared_notices=missing,
                _rows=rows,
            )
            for relative in relevant:
                owners.setdefault(relative, []).append((key, rows[relative]))
        except (OSError, ValueError, UnicodeError):
            errors.append(
                dict(code="distribution_metadata_unreadable_or_invalid", metadata_id=info.name)
            )
    return owners, packages, errors


def reconcile(run_id):
    if re.fullmatch(r"[a-z0-9]{1,16}", run_id) is None:
        raise ValueError("invalid_run_id")
    target = OUT / f"runtime-reconciliation-{run_id}.json"
    if target.exists():
        raise ValueError("preserve_prior_evidence")
    start = time.monotonic()
    selection = strict_json_load_path(
        OUT / "observed-serving-selection-cpu02.json", max_bytes=2_000_000
    )
    trace = strict_json_load_path(OUT / "serving-trace-cpu02-3.json", max_bytes=2_000_000)
    required = set(trace["modules"]) | set(trace["native_mappings"])
    missing = selection["unaccounted_observed_runtime_paths"]
    prefix = "package_runtime/Lib/site-packages/"
    wanted = {p.removeprefix(prefix).casefold() for p in missing if p.startswith(prefix)}
    site = selected_runtime_site()
    owners, packages, metadata_errors = build_ownership(site, wanted)
    roots = dict(package_runtime=site.parents[1], python_runtime=Path(sys.base_prefix))
    report = dict(
        schema="compact_runtime_reconciliation_v1",
        origin_verified=False,
        runtime_qualified=False,
        ga_ready=False,
        production_admitted=False,
        model_copy_bytes=0,
        runtime_copy_bytes=0,
        downloads=0,
        files=[],
        packages=[],
        blockers=[],
        optional_missing_attempts=[],
        metadata_scan_errors=metadata_errors,
    )
    for index, logical in enumerate(missing, 1):
        if time.monotonic() - start > 240:
            report["blockers"].append(
                dict(code="reconciliation_time_budget", remaining=len(missing) - index + 1)
            )
            break
        if not logical.startswith(prefix):
            report["blockers"].append(dict(code="unaccounted_python_runtime", path=logical))
            continue
        relative = logical.removeprefix(prefix)
        if not safe_relative(relative):
            report["blockers"].append(dict(code="unsafe_observed_path"))
            continue
        path = site / relative
        if not path.exists() and logical not in required:
            report["optional_missing_attempts"].append(logical)
            continue
        candidates = owners.get(relative.casefold(), [])
        if len(candidates) != 1:
            report["blockers"].append(dict(code="ownership_missing_or_ambiguous", path=logical))
            continue
        package, entry = candidates[0]
        try:
            item = file_record(
                path, roots, expected_hash=entry["hash"], expected_size=entry["size"]
            )
            item.update(package=package, actually_imported_or_mapped=logical in required)
            report["files"].append(item)
            if not entry["hash"]:
                if (
                    relative == package + "/RECORD"
                    and item["sha256"] == packages[package]["record_sha256"]
                ):
                    item["integrity_basis"] = (
                        "record_self_entry_snapshot_not_publisher_authentication"
                    )
                else:
                    report["blockers"].append(
                        dict(code="installed_record_hash_absent", path=logical)
                    )
        except (OSError, ValueError):
            report["blockers"].append(dict(code="installed_record_integrity_failed", path=logical))
        if index % 200 == 0:
            print(json.dumps(dict(inspected=index, total=len(missing))), flush=True)
    for key, package in packages.items():
        package["actually_imported_or_mapped"] = any(
            r["package"] == key and r["actually_imported_or_mapped"] for r in report["files"]
        )
        rows = package.pop("_rows")
        package["notices"] = []
        for name in package.pop("notice_paths"):
            entry = rows[name.casefold()]
            try:
                package["notices"].append(
                    file_record(
                        site / name, roots, expected_hash=entry["hash"], expected_size=entry["size"]
                    )
                )
            except (OSError, ValueError):
                report["blockers"].append(dict(code="notice_integrity_failed", package=key))
        if not package["notices"] or package["missing_declared_notices"]:
            report["blockers"].append(
                dict(
                    code="notice_missing",
                    package=key,
                    scope="imported_runtime"
                    if package["actually_imported_or_mapped"]
                    else "metadata_observation_only",
                )
            )
        report["packages"].append(dict(metadata_id=key, **package))
    all_files = {row["path"]: row for row in report["files"]}
    for package in report["packages"]:
        all_files.update({row["path"]: row for row in package["notices"]})
    already = {row["path"] for row in selection["files"]}
    additional_bytes = sum(row["bytes"] for name, row in all_files.items() if name not in already)
    report.update(
        files_checked=len(report["files"]),
        packages_identified=len(packages),
        added_distinct_bytes=additional_bytes,
        accounted_model_plus_runtime_bytes=selection["selected_bytes"]
        + sum(size for size, _ in PINNED.values())
        + additional_bytes,
        record_self_entry_snapshots=sum(
            r.get("integrity_basis") == "record_self_entry_snapshot_not_publisher_authentication"
            for r in report["files"]
        ),
        record_file_specification="https://packaging.python.org/en/latest/specifications/recording-installed-packages/#the-record-file",
        duration_seconds=round(time.monotonic() - start, 3),
    )
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"files", "packages", "optional_missing_attempts"}
            }
        )
    )
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    reconcile(parser.parse_args().run_id)
