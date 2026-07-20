#!/usr/bin/env python3
"""Build a deterministic, audited full source ZIP.

The builder sorts entries, fixes ZIP timestamps and permissions, rejects
symlinks/path traversal, excludes runtime/private/model artifacts, and embeds a
hash manifest. Bundled public FOCAF PDFs are the only allowed PDF payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

EXCLUDED_DIRS = {
    ".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", "__pycache__",
    ".venv", "venv", "node_modules", "dist", "build", "runtime", "uploads",
    "vectorstores", "corpora", "official_authority_store", "parsed_authority_store",
    "embedding_store", "matter_store", "eval_store", "audit_store", "model_registry",
    ".local_data", ".mfl_work", "models", "weights",
}
EXCLUDED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".faiss", ".bin", ".pt", ".pth", ".onnx",
    ".safetensors", ".gguf", ".pyc", ".pyo",
}
EXCLUDED_NAMES = {".env", "source_sbom.json", "source_release_lock.json", "RELEASE_SOURCE_MANIFEST.json"}
ALLOWED_PDF_PREFIXES = {
    "src/maine_family_law_llm/resources/focaf/",
    "maine_family_law_llm/resources/focaf/",
}
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _allowed_pdf(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_PDF_PREFIXES)


def _include(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    parts = PurePosixPath(rel).parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.name.endswith(".local.json") and rel != "store/msix/identity.local.json":
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if path.suffix.casefold() == ".pdf" and not _allowed_pdf(rel):
        return False
    if path.name.startswith("smoke_evidence") and path.suffix.casefold() == ".json":
        return False
    return True


def collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink_not_allowed:{path.relative_to(repo_root).as_posix()}")
        if not path.is_file() or not _include(path, repo_root):
            continue
        rel = path.relative_to(repo_root).as_posix()
        pure = PurePosixPath(rel)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"unsafe_relative_path:{rel}")
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(repo_root).as_posix().casefold())


def build_release(repo_root: Path, output: Path, archive_root: str) -> dict:
    repo_root = repo_root.resolve()
    output = output.resolve()
    archive_root = str(archive_root or "ME_FM_LLM").strip("/\\")
    if not archive_root or ".." in PurePosixPath(archive_root).parts:
        raise ValueError("invalid_archive_root")

    files = collect_files(repo_root)
    entries: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = path.relative_to(repo_root).as_posix()
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            entries.append({"path": rel, "size": len(data), "sha256": digest})
            info = ZipInfo(f"{archive_root}/{rel}", date_time=FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, data)

        manifest = {
            "schema_version": "deterministic_source_release_manifest_v1",
            "archive_root": archive_root,
            "file_count": len(entries),
            "total_uncompressed_bytes": sum(int(item["size"]) for item in entries),
            "public_focaf_pdf_count": sum(1 for item in entries if str(item["path"]).endswith(".pdf")),
            "runtime_private_or_model_artifacts_included": False,
            "entries": entries,
        }
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        info = ZipInfo(f"{archive_root}/RELEASE_SOURCE_MANIFEST.json", date_time=FIXED_TIMESTAMP)
        info.compress_type = ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        info.create_system = 3
        archive.writestr(info, manifest_bytes)

    zip_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "schema_version": "deterministic_source_release_result_v1",
        "status": "pass",
        "output": str(output),
        "archive_root": archive_root,
        "file_count": len(entries),
        "manifest_entry_count": len(entries),
        "zip_sha256": zip_sha256,
        "zip_size": output.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-root", default="ME_FM_LLM")
    args = parser.parse_args()
    report = build_release(args.repo_root, args.output, args.archive_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
