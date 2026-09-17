"""One research-only, RECORD-checked BERT Python overlay, not an installed runtime.

Copies only the selected Transformers Python files and notices into repository
dist. No model/native/Python-runtime duplication, external edits or admission.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from legal.security.strict_json import strict_json_loads
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT
from scripts.audit_compact_ranker_runtime import file_record, license_paths

DIRECTORY = OUTPUT / "bert-python-overlay"
VERSION = "5.14.1"
MAX_BYTES = 10_000_000
MANIFEST_NAME = "overlay-manifest-v2.json"


def no_links(path):
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("overlay_link_forbidden")


def overlay_path(directory, name):
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or name != relative.as_posix()
        or ".." in relative.parts
        or not relative.parts
        or any(
            re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,159}", p) is None for p in relative.parts
        )
    ):
        raise ValueError("overlay_record_path_invalid")
    target = directory / relative
    no_links(target)
    if not target.resolve().is_relative_to(ROOT / "dist"):
        raise ValueError("overlay_repository_dist_required")
    return target


def selected_name(name):
    path = PurePosixPath(name)
    if (
        name != path.as_posix()
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
    ):
        raise ValueError("overlay_record_path_invalid")
    if len(path.parts) < 2 or path.parts[0] != "transformers" or path.suffix != ".py":
        return False
    return (
        path.parts[1] != "models"
        or name == "transformers/models/__init__.py"
        or (len(path.parts) >= 3 and path.parts[2] in {"auto", "bert", "encoder_decoder"})
    )


def prepare(*, build=False, dist=None, directory=DIRECTORY):
    dist = metadata.distribution("transformers") if dist is None else dist
    if dist.version != VERSION or dist.metadata.get("Name") != "transformers":
        raise ValueError("overlay_runtime_version_mismatch")
    entries = list(dist.files or ())
    by_name = {str(p).replace("\\", "/"): p for p in entries}
    notices, missing = license_paths(dist, set(by_name))
    if not notices or missing:
        raise ValueError("overlay_notice_inventory_incomplete")
    # pip also records console scripts outside site-packages. They are not
    # selected; never normalize/copy those paths into this Python-only overlay.
    selected = [
        name for name in by_name if name.startswith("transformers/") and selected_name(name)
    ]
    required = {
        "transformers/__init__.py",
        "transformers/models/__init__.py",
        "transformers/models/bert/modeling_bert.py",
        "transformers/models/bert/tokenization_bert.py",
        "transformers/models/auto/modeling_auto.py",
    }
    if not required.issubset(selected):
        raise ValueError("overlay_selection_incomplete")
    names = [(name, name) for name in sorted(selected)] + [
        (name, f"notices/transformers-{i}-{Path(name).name}") for i, name in enumerate(notices)
    ]
    total = sum(by_name[name].size or 0 for name, _ in names)
    if not 0 < total < MAX_BYTES or len(names) > 400:
        raise ValueError("overlay_size_budget_exceeded")
    root = Path(dist.locate_file("")).resolve(strict=True)
    report = {
        "schema": "compact_bert_python_overlay_v1",
        "version": VERSION,
        "selection": "common_python_plus_bert_auto_encoder_decoder",
        "bytes": total,
        "production_admitted": False,
        "ga_ready": False,
        "publisher_authenticated": False,
        "record_consistency_only": True,
        "files": [],
    }
    for name, destination in names:
        entry = by_name[name]
        if entry.hash is None or entry.size is None:
            raise ValueError("overlay_unhashed_source_forbidden")
        source = Path(dist.locate_file(entry))
        no_links(source)
        record = file_record(
            source, {"installed": root}, expected_hash=entry.hash, expected_size=entry.size
        )
        target = overlay_path(directory, destination)
        row = {
            "path": destination,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
            "installed_record_path": name,
        }
        if build:
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("overlay_source_changed")
            if target.exists():
                if target.stat().st_size != len(raw) or target.read_bytes() != raw:
                    raise ValueError("preserve_changed_overlay_file")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
        report["files"].append(row)
    if build:
        target = overlay_path(directory, MANIFEST_NAME)
        raw = json.dumps(report, indent=2).encode() + b"\n"
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError("preserve_prior_overlay_manifest")
        else:
            with target.open("xb") as stream:
                stream.write(raw)
    return report


def verify(directory=DIRECTORY, *, dist=None):
    """No unlisted Python files or mutable per-user cache may enter this overlay."""
    manifest = overlay_path(directory, MANIFEST_NAME)
    if manifest.stat().st_size > 200_000:
        raise ValueError("overlay_manifest_budget_exceeded")
    report = strict_json_loads(manifest.read_bytes(), max_bytes=200_000, require_object=True)
    # A self-reported hash list is not trust. Recheck the selected installed
    # RECORD payload and compare the entire expected manifest on every use.
    expected = prepare(build=False, dist=dist, directory=directory)
    if report != expected:
        raise ValueError("overlay_manifest_does_not_match_installed_selection")
    if report.get("version") != VERSION or report.get("production_admitted") is not False:
        raise ValueError("overlay_manifest_invalid")
    names = {r["path"] for r in report["files"]}
    if len(names) != len(report["files"]) or len(names) > 400:
        raise ValueError("overlay_inventory_invalid")
    actual = set()
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            no_links(Path(parent) / name)
        actual.update((Path(parent) / name).relative_to(directory).as_posix() for name in files)
    # Preserve the first failed selection's metadata, not a second runtime copy.
    if actual - {"overlay-manifest.json"} != names | {MANIFEST_NAME}:
        raise ValueError("overlay_unlisted_file")
    total = 0
    for row in report["files"]:
        name = row["path"]
        path = PurePosixPath(name)
        if not selected_name(name) and not (len(path.parts) == 2 and path.parts[0] == "notices"):
            raise ValueError("overlay_inventory_invalid")
        target = overlay_path(directory, name)
        if target.stat().st_size != row["bytes"]:
            raise ValueError("overlay_file_changed")
        raw = target.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("overlay_file_changed")
        total += len(raw)
    if total != report["bytes"] or not 0 < total < MAX_BYTES:
        raise ValueError("overlay_size_budget_exceeded")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    result = prepare(build=args.build)
    if args.build:
        verify()
    print(
        json.dumps(
            {
                "bytes": result["bytes"],
                "files": len(result["files"]),
                "built": args.build,
                "ga_ready": False,
            }
        )
    )
