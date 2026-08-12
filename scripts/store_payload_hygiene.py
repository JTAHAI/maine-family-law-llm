"""Release hygiene for the mutable runtime and sealed MSIX payload.

This module intentionally imports only the Python standard library.  It is used before
and after every Store packaging boundary so its own execution cannot regenerate bundled
engine bytecode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import urllib.parse
import zipfile
from xml.etree import ElementTree
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


BYTECODE_NAME = re.compile(r"(?i)(?:\.py[co](?:\..+)?$|.*-pytest-.*\.pyc(?:\..+)?$)")
EXPLICIT_TEST_TREES = {
    "_internal/spacy/tests",
    "_internal/thinc/tests",
    "_internal/thinc/extra/tests",
    "_internal/torch/fx/passes/tests",
    "_internal/torch/testing/_internal/optests",
}
CLEANUP_RULES = [
    "__pycache__ directories",
    "*.pyc, *.pyo, and *.pyc.* files",
    "pytest-tagged bytecode",
    ".pytest_cache directories",
    "known package-local test trees",
]


def utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_root(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise RuntimeError(f"Approved root is not a directory: {resolved}")
    return resolved


def safe_relative(root: Path, path: Path) -> Path:
    try:
        return path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Candidate escaped approved root: {path}") from exc


def is_reparse_or_symlink(path: Path) -> bool:
    return path.is_symlink() or bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def iter_tree(root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            candidate = current / name
            if is_reparse_or_symlink(candidate):
                raise RuntimeError(f"Reparse point is not allowed in release payload: {candidate}")
        for name in filenames:
            candidate = current / name
            if is_reparse_or_symlink(candidate):
                raise RuntimeError(f"Reparse point is not allowed in release payload: {candidate}")
            yield candidate


def residue_kind(root: Path, path: Path) -> str | None:
    rel = safe_relative(root, path).as_posix().lower()
    parts = rel.split("/")
    if "__pycache__" in parts:
        return "bytecode_cache"
    if ".pytest_cache" in parts:
        return "pytest_cache"
    if BYTECODE_NAME.match(path.name):
        return "bytecode_file"
    if any(rel == test_root or rel.startswith(test_root + "/") for test_root in EXPLICIT_TEST_TREES):
        return "package_test_tree"
    return None


def collect_residues(root: Path) -> list[tuple[Path, str]]:
    results: list[tuple[Path, str]] = []
    for path in iter_tree(root):
        kind = residue_kind(root, path)
        if kind:
            results.append((path, kind))
    return results


def file_manifest(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(iter_tree(root), key=lambda item: item.as_posix().casefold()):
        rel = safe_relative(root, path).as_posix()
        rows.append({"path": rel, "size": path.stat().st_size, "sha256": sha256_file(path)})
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def clean(root: Path, output: Path) -> int:
    root = resolve_root(root)
    candidates: dict[Path, str] = {}
    for path in iter_tree(root):
        kind = residue_kind(root, path)
        if kind:
            candidates[path] = kind
    removed: list[dict[str, Any]] = []
    for path, kind in sorted(candidates.items(), key=lambda item: len(item[0].parts), reverse=True):
        if not path.exists():
            continue
        safe_relative(root, path)
        if is_reparse_or_symlink(path):
            raise RuntimeError(f"Refusing to delete reparse point: {path}")
        removed.append(
            {
                "path": safe_relative(root, path).as_posix(),
                "kind": kind,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
        path.unlink()
    # Cache and test-tree directories are now empty or partially empty. Remove only
    # directories that independently match an approved cleanup rule.
    for directory, dirnames, _ in os.walk(root, topdown=False, followlinks=False):
        candidate = Path(directory)
        rel = safe_relative(root, candidate).as_posix().lower()
        if candidate == root:
            continue
        directory_rule = candidate.name.lower() in {"__pycache__", ".pytest_cache"} or rel in EXPLICIT_TEST_TREES
        if directory_rule:
            if is_reparse_or_symlink(candidate):
                raise RuntimeError(f"Refusing to delete reparse point: {candidate}")
            shutil.rmtree(candidate, ignore_errors=False)
    remaining = [safe_relative(root, path).as_posix() for path, _ in collect_residues(root)]
    payload = {
        "schema_version": "store_payload_cleanup_v1",
        "generated_at": utcnow(),
        "root": str(root),
        "cleanup_rules_applied": CLEANUP_RULES,
        "removed_files": removed,
        "removed_file_count": len(removed),
        "removed_bytes": sum(int(row["size"]) for row in removed),
        "remaining_prohibited_residues": remaining,
        "status": "pass" if not remaining else "fail",
    }
    write_json(output, payload)
    if remaining:
        raise RuntimeError(f"Cleanup left prohibited residues under {root}: {remaining[:3]}")
    return 0


def snapshot(root: Path, output: Path, checkpoint: str, command: str, parent_command: str) -> int:
    root = resolve_root(root)
    payload: dict[str, Any]
    if output.exists():
        payload = json.loads(output.read_text(encoding="utf-8"))
    else:
        payload = {"schema_version": "bytecode_regeneration_trace_v1", "checkpoints": [], "new_files": []}
    prior = {
        row["relative_path"]
        for entry in payload["checkpoints"]
        for row in entry.get("residues", [])
    }
    residues = []
    for path, kind in collect_residues(root):
        rel = safe_relative(root, path).as_posix()
        residues.append({"relative_path": rel, "kind": kind, "size": path.stat().st_size, "sha256": sha256_file(path)})
    residues.sort(key=lambda row: str(row["relative_path"]).casefold())
    entry = {"checkpoint": checkpoint, "timestamp": utcnow(), "root": str(root), "residues": residues}
    payload["checkpoints"].append(entry)
    for row in residues:
        if row["relative_path"] not in prior:
            payload["new_files"].append(
                {
                    "checkpoint_first_observed": checkpoint,
                    "relative_path": row["relative_path"],
                    "size": row["size"],
                    "sha256": row["sha256"],
                    "creating_process_or_command": command,
                    "parent_process": parent_command or f"pid:{os.getppid()}",
                    "required_at_runtime": False,
                }
            )
    payload["generated_at"] = utcnow()
    write_json(output, payload)
    return 0


def seal(root: Path, output: Path, cleanup_evidence: list[str]) -> int:
    root = resolve_root(root)
    residues = [safe_relative(root, path).as_posix() for path, _ in collect_residues(root)]
    if residues:
        raise RuntimeError(f"Cannot seal payload containing prohibited residues: {residues[:3]}")
    files = file_manifest(root)
    serialized = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = {
        "schema_version": "sealed_msix_payload_v1",
        "timestamp": utcnow(),
        "staging_root": str(root),
        "file_count": len(files),
        "total_bytes": sum(int(row["size"]) for row in files),
        "manifest_sha256": hashlib.sha256(serialized).hexdigest(),
        "files": files,
        "cleanup_rules_applied": CLEANUP_RULES,
        "cleanup_evidence": cleanup_evidence,
        "status": "pass",
    }
    write_json(output, payload)
    return 0


def verify(root: Path, seal_path: Path, output: Path) -> int:
    root = resolve_root(root)
    sealed = json.loads(seal_path.read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in sealed["files"]}
    actual = {row["path"]: row for row in file_manifest(root)}
    added = sorted(set(actual) - set(expected))
    deleted = sorted(set(expected) - set(actual))
    changed = sorted(path for path in set(actual) & set(expected) if actual[path] != expected[path])
    residues = [safe_relative(root, path).as_posix() for path, _ in collect_residues(root)]
    payload = {
        "schema_version": "sealed_msix_payload_audit_v1",
        "generated_at": utcnow(),
        "staging_root": str(root),
        "seal": str(seal_path),
        "added_files": added,
        "deleted_files": deleted,
        "changed_files": changed,
        "prohibited_residues": residues,
        "status": "pass" if not added and not deleted and not changed and not residues else "fail",
    }
    write_json(output, payload)
    if payload["status"] != "pass":
        raise RuntimeError("Sealed payload changed after sealing.")
    return 0


def verify_archive(msix_path: Path, seal_path: Path, output: Path) -> int:
    sealed = json.loads(seal_path.read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in sealed["files"]}
    metadata_paths = {"[Content_Types].xml", "AppxBlockMap.xml", "AppxSignature.p7x"}
    with zipfile.ZipFile(msix_path) as archive:
        actual = {}
        for entry in archive.infolist():
            if entry.is_dir() or entry.filename.startswith("AppxMetadata/") or entry.filename in metadata_paths:
                continue
            package_path = urllib.parse.unquote(entry.filename)
            content = archive.read(entry)
            # MakeAppx serializes the supplied manifest into its canonical UTF-8
            # container form. Compare its decoded text rather than its BOM choice.
            if package_path == "AppxManifest.xml":
                content = canonical_xml(content)
            actual[package_path] = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    if "AppxManifest.xml" in expected:
        manifest_path = Path(sealed["staging_root"]) / "AppxManifest.xml"
        content = canonical_xml(manifest_path.read_bytes())
        expected["AppxManifest.xml"] = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    added = sorted(set(actual) - set(expected))
    deleted = sorted(set(expected) - set(actual))
    changed = sorted(path for path in set(actual) & set(expected) if actual[path] != {"size": expected[path]["size"], "sha256": expected[path]["sha256"]})
    payload = {
        "schema_version": "sealed_msix_archive_audit_v1",
        "generated_at": utcnow(),
        "msix_path": str(msix_path),
        "seal": str(seal_path),
        "added_files": added,
        "deleted_files": deleted,
        "changed_files": changed,
        "status": "pass" if not added and not deleted and not changed else "fail",
    }
    write_json(output, payload)
    if payload["status"] != "pass":
        raise RuntimeError("MSIX payload does not match the sealed staging manifest.")
    return 0


def canonical_xml(content: bytes) -> bytes:
    """Normalizes MakeAppx's harmless XML formatting and declaration rewrite."""
    root = ElementTree.fromstring(content)

    def normalize(element: ElementTree.Element) -> None:
        element.attrib = dict(sorted(element.attrib.items()))
        element.text = element.text.strip() if element.text and element.text.strip() else None
        element.tail = None
        for child in element:
            normalize(child)

    normalize(root)
    return ElementTree.tostring(root, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    clean_parser = commands.add_parser("clean")
    clean_parser.add_argument("--root", required=True)
    clean_parser.add_argument("--output", required=True)
    snapshot_parser = commands.add_parser("snapshot")
    snapshot_parser.add_argument("--root", required=True)
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.add_argument("--checkpoint", required=True)
    snapshot_parser.add_argument("--command", required=True)
    snapshot_parser.add_argument("--parent-command", default="")
    seal_parser = commands.add_parser("seal")
    seal_parser.add_argument("--root", required=True)
    seal_parser.add_argument("--output", required=True)
    seal_parser.add_argument("--cleanup-evidence", action="append", default=[])
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--root", required=True)
    verify_parser.add_argument("--seal", required=True)
    verify_parser.add_argument("--output", required=True)
    archive_parser = commands.add_parser("verify-archive")
    archive_parser.add_argument("--msix-path", required=True)
    archive_parser.add_argument("--seal", required=True)
    archive_parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "clean":
        return clean(Path(args.root), Path(args.output))
    if args.action == "snapshot":
        return snapshot(Path(args.root), Path(args.output), args.checkpoint, args.command, args.parent_command)
    if args.action == "seal":
        return seal(Path(args.root), Path(args.output), args.cleanup_evidence)
    if args.action == "verify-archive":
        return verify_archive(Path(args.msix_path), Path(args.seal), Path(args.output))
    return verify(Path(args.root), Path(args.seal), Path(args.output))


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
