from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


BLOCKED_PATH_FRAGMENTS = [
    ".git/",
    "__pycache__/",
    "tests/",
    ".venv/",
    "venv/",
    "uploads/",
    "official_authority_store/",
    "parsed_authority_store/",
    "embedding_store/",
    "eval_store/",
    "vector_store/",
    "vectorstores/",
    "matter_store/",
    "runtime_data/",
    "logs/",
    "private_forensic_master",
]
BLOCKED_SUFFIXES = [
    ".db",
    ".sqlite",
    ".sqlite3",
    ".gguf",
    ".safetensors",
    ".pfx",
    ".cer",
    ".pvk",
    ".key",
    ".pem",
    ".log",
    ".tmp",
]
TEXT_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".csv", ".html", ".htm", ".xml", ".config", ".ps1", ".cmd", ".vbs", ".py"}
ABSOLUTE_PATH_MARKERS = ["C:\\Users\\", "C:\\dev\\", "D:\\dev\\", "E:\\", "F:\\", "G:\\", "H:\\"]
ALLOWED_PEM_PATHS = {"_internal/certifi/cacert.pem"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_manifest(stage_root: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for path in sorted(p for p in stage_root.rglob("*") if p.is_file()):
        rel = path.relative_to(stage_root).as_posix()
        results.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return results


def audit_stage(stage_root: Path) -> dict[str, object]:
    manifest = package_manifest(stage_root)
    blocked_paths = []
    blocked_files = []
    absolute_path_hits = []
    for row in manifest:
        rel = str(row["path"]).lower()
        if any(fragment in rel for fragment in BLOCKED_PATH_FRAGMENTS):
            blocked_paths.append(row["path"])
        if rel in ALLOWED_PEM_PATHS:
            pass
        elif any(rel.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
            blocked_files.append(row["path"])
        path = stage_root / str(row["path"]).replace("/", os.sep)
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for marker in ABSOLUTE_PATH_MARKERS:
                if marker in text:
                    absolute_path_hits.append({"path": row["path"], "marker": marker})
    return {
        "status": "pass" if not blocked_paths and not blocked_files and not absolute_path_hits else "fail",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "blocked_paths": blocked_paths,
        "blocked_files": blocked_files,
        "absolute_path_hits": absolute_path_hits,
        "packaged_file_count": len(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--sha-output", default="")
    parser.add_argument("--msix-path", default="")
    args = parser.parse_args()

    stage_root = Path(args.stage_root)
    manifest = package_manifest(stage_root)
    audit = audit_stage(stage_root)
    manifest_path = Path(args.manifest_output)
    audit_path = Path(args.audit_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if args.msix_path and args.sha_output:
        msix_path = Path(args.msix_path)
        sha_path = Path(args.sha_output)
        sha_path.parent.mkdir(parents=True, exist_ok=True)
        sha_path.write_text(f"{sha256_file(msix_path)}  {msix_path.name}\n", encoding="utf-8")
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
