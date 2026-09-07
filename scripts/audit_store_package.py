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
    "model_store/",
    "model_registry/",
    "benchmark_runs/",
    "runtime_profiles/",
    "quarantine/",
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
    ".pyc",
    ".pyo",
]
TEXT_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".csv", ".html", ".htm", ".xml", ".config", ".ps1", ".cmd", ".vbs", ".py"}
ABSOLUTE_PATH_MARKERS = ["C:\\Users\\", "C:\\dev\\", "D:\\dev\\", "E:\\", "F:\\", "G:\\", "H:\\"]
ALLOWED_PEM_PATHS = {
    "_internal/certifi/cacert.pem",
    "_internal/grpc/_cython/_credentials/roots.pem",
}
ALLOWED_PUBLIC_MODEL_PREFIXES = (
    "store/docling/models/",
    "_internal/store/fast-interchange/",
)
ALLOWED_PUBLIC_MODEL_SUFFIXES = (
    ".safetensors",
)
SPECIALIST_PREFIX = "_internal/store/fast-interchange/"
SPECIALIST_RECEIPT = "_internal/store/bundled-specialist-validation.json"
ALLOWED_ABSOLUTE_PATH_HITS = {
    "_internal/torch/_appdirs.py",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text_atomic(path: Path, content: str) -> None:
    """Publish release evidence only after a complete write succeeds.

    A cancelled package audit must leave an absent final receipt (and a clearly
    disposable sibling temporary file), not a partial or zero-filled JSON file
    that could later be mistaken for evidence.
    """
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


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


def specialist_tree_identity(rows: list[dict[str, object]]) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    total = 0
    for row in sorted(rows, key=lambda item: str(item["path"])):
        relative = str(row["path"])[len(SPECIALIST_PREFIX) :]
        size = int(row["size"])
        digest.update(f"{relative}\0{size}\0{row['sha256']}\n".encode())
        total += size
    return digest.hexdigest(), len(rows), total


def specialist_receipt_failures(
    stage_root: Path, manifest: list[dict[str, object]]
) -> list[str]:
    specialist_rows = [
        row for row in manifest if str(row["path"]).lower().startswith(SPECIALIST_PREFIX)
    ]
    receipt_path = stage_root / SPECIALIST_RECEIPT.replace("/", os.sep)
    if not specialist_rows:
        return ["orphaned_bundled_specialist_validation_receipt"] if receipt_path.is_file() else []
    if not receipt_path.is_file():
        return ["bundled_specialist_validation_receipt_missing"]
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["bundled_specialist_validation_receipt_invalid"]
    tree_sha256, file_count, total_bytes = specialist_tree_identity(specialist_rows)
    expected = {
        "status": "pass",
        "capabilities": ["drafting", "evidence_review"],
        "production_signed_admission": True,
        "attorney_reviewed_evaluation": True,
        "redistribution_permitted": True,
        "runtime_versions_matched": True,
        "cpu_fallback_runtime_compatible": True,
        "review_required": True,
        "tree_sha256": tree_sha256,
        "file_count": file_count,
        "total_bytes": total_bytes,
    }
    failures = [
        f"bundled_specialist_validation_mismatch:{name}"
        for name, value in expected.items()
        if receipt.get(name) != value
    ]
    return failures


def audit_stage(stage_root: Path, forbidden_values: list[str]) -> dict[str, object]:
    manifest = package_manifest(stage_root)
    specialist_failures = specialist_receipt_failures(stage_root, manifest)
    blocked_paths = []
    blocked_files = []
    absolute_path_hits = []
    private_information = []
    prohibited_residues = []
    public_runtime_assets = []
    harmless_source_literals = []
    for row in manifest:
        rel = str(row["path"]).lower()
        if any(fragment in rel for fragment in BLOCKED_PATH_FRAGMENTS):
            blocked_paths.append(row["path"])
            prohibited_residues.append({"path": row["path"], "reason": "prohibited_packaging_residue"})
        is_public_model = rel.startswith(ALLOWED_PUBLIC_MODEL_PREFIXES) and rel.endswith(ALLOWED_PUBLIC_MODEL_SUFFIXES)
        if rel in ALLOWED_PEM_PATHS:
            public_runtime_assets.append({"path": row["path"], "reason": "public_ca_bundle"})
        elif is_public_model:
            public_runtime_assets.append({"path": row["path"], "reason": "bundled_offline_model"})
        elif any(rel.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
            blocked_files.append(row["path"])
            prohibited_residues.append({"path": row["path"], "reason": "prohibited_file_type"})
        path = stage_root / str(row["path"]).replace("/", os.sep)
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for marker in ABSOLUTE_PATH_MARKERS:
                if marker in text and row["path"] not in ALLOWED_ABSOLUTE_PATH_HITS:
                    absolute_path_hits.append({"path": row["path"], "marker": marker})
                    private_information.append({"path": row["path"], "reason": "absolute_path_marker", "value": marker})
                elif marker in text:
                    harmless_source_literals.append({"path": row["path"], "value": marker})
            for value in forbidden_values:
                if value and value in text:
                    private_information.append({"path": row["path"], "reason": "forbidden_build_value", "value": value})
    return {
        "status": (
            "pass"
            if not blocked_paths
            and not blocked_files
            and not absolute_path_hits
            and not private_information
            and not specialist_failures
            else "fail"
        ),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "blocked_paths": blocked_paths,
        "blocked_files": blocked_files,
        "absolute_path_hits": absolute_path_hits,
        "private_or_machine_specific_information": private_information,
        "prohibited_build_or_test_artifacts": prohibited_residues,
        "required_public_runtime_assets": public_runtime_assets,
        "bundled_specialist_validation_failures": specialist_failures,
        "harmless_source_code_literals": harmless_source_literals,
        "packaged_file_count": len(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--sha-output", default="")
    parser.add_argument("--msix-path", default="")
    parser.add_argument("--forbidden-path", action="append", default=[])
    args = parser.parse_args()

    stage_root = Path(args.stage_root)
    manifest = package_manifest(stage_root)
    audit = audit_stage(stage_root, args.forbidden_path)
    manifest_path = Path(args.manifest_output)
    audit_path = Path(args.audit_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(manifest_path, json.dumps(manifest, indent=2) + "\n")
    write_text_atomic(audit_path, json.dumps(audit, indent=2) + "\n")

    if args.msix_path and args.sha_output:
        msix_path = Path(args.msix_path)
        sha_path = Path(args.sha_output)
        sha_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(sha_path, f"{sha256_file(msix_path)}  {msix_path.name}\n")
    return 0 if audit["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
