"""Release tree artifact hygiene audit.

The source repository must remain a clean source package. Evidence JSON, SBOMs,
release locks, smoke reports, local reports, corpora, vector indexes, model files,
and matter data are generated artifacts and must be written to explicit output
paths or external data/evidence roots instead of living at the repo root.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT_GENERATED_JSON_PREFIXES = ("smoke_evidence",)
ROOT_GENERATED_JSON_NAMES = {
    "enterprise_acceptance_evidence.json",
    "full_ga_workbench_report.json",
    "local_smoke_report.json",
    "local_test_readiness_report.json",
    "networked_source_gate_report.json",
    "operator_handoff_bundle.json",
    "operator_test_battery_evidence.json",
    "post_ga_repo_review_build_path.json",
    "production_promotion_gate_report.json",
    "public_attribution_kit_report.json",
    "reboot_recovery_healthcheck.json",
    "source_release_lock.json",
    "source_sbom.json",
}

PROHIBITED_RELEASE_DIR_NAMES = {
    "official_authority_store",
    "parsed_authority_store",
    "embedding_store",
    "matter_store",
    "eval_store",
    "audit_store",
    "model_registry",
    "runtime",
    "uploads",
    "vectorstores",
    "corpora",
    "models",
    "weights",
}

PROHIBITED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".faiss",
    ".bin",
    ".pt",
    ".pth",
    ".onnx",
    ".safetensors",
    ".gguf",
    ".pdf",
}


APPROVED_PUBLIC_PDF_ROOTS = (
    Path("src/maine_family_law_llm/resources/focaf"),
    Path("maine_family_law_llm/resources/focaf"),
)

# These are version-controlled source inputs.  ``legal/runtime`` is an
# implementation package (not a persisted runtime directory), while the two
# fixture roots intentionally carry malformed binaries to prove parser
# quarantine behavior.  Release assembly has a separate exact-package audit;
# this source-tree audit must not mistake either for operator data.
PUBLIC_SOURCE_DIRECTORY_PREFIXES = {
    ("legal", "runtime"),
}
PUBLIC_FIXTURE_DIRECTORY_PREFIXES = {
    ("data", "fixtures"),
    ("tests", "fixtures"),
}


def _has_prefix(parts: tuple[str, ...], prefixes: set[tuple[str, ...]]) -> bool:
    return any(parts[: len(prefix)] == prefix for prefix in prefixes)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_approved_public_pdf(root: Path, path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    for root_rel in APPROVED_PUBLIC_PDF_ROOTS:
        try:
            within = rel.relative_to(root_rel)
        except ValueError:
            continue
        if len(within.parts) != 1:
            return False
        inventory_path = root / root_rel / "focaf_inventory.json"
        try:
            payload = json.loads(inventory_path.read_text(encoding="utf-8"))
            expected = {
                str(row.get("original_filename") or ""): str(row.get("source_hash") or "").lower()
                for row in payload.get("documents", [])
            }.get(within.name, "")
            return bool(expected) and path.read_bytes()[:5] == b"%PDF-" and _sha256(path).lower() == expected
        except (OSError, json.JSONDecodeError):
            return False
    return False

IGNORED_TREE_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    ".mfl_work",
    "dist",
    "build",
    "node_modules",
}


@dataclass(frozen=True)
class ReleaseArtifactAudit:
    repo_root: Path

    def audit(self) -> dict[str, Any]:
        root = self.repo_root.resolve()
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        for path in sorted(root.rglob("*")):
            if not path.exists():
                continue
            rel = path.relative_to(root)
            rel_posix = rel.as_posix()
            if any(part in IGNORED_TREE_PARTS or part.endswith(".egg-info") for part in rel.parts):
                continue
            is_public_runtime_source = _has_prefix(rel.parts, PUBLIC_SOURCE_DIRECTORY_PREFIXES)
            is_public_fixture = _has_prefix(rel.parts, PUBLIC_FIXTURE_DIRECTORY_PREFIXES)
            if path.is_dir() and path.name in PROHIBITED_RELEASE_DIR_NAMES and not is_public_runtime_source:
                blockers.append({"path": rel_posix, "reason": "external_artifact_directory_in_repo"})
                continue
            if path.is_file() and path.suffix.lower() in PROHIBITED_SUFFIXES:
                if is_public_fixture:
                    continue
                if path.suffix.lower() == ".pdf" and _is_approved_public_pdf(root, path):
                    continue
                blockers.append({"path": rel_posix, "reason": "prohibited_release_file_type"})
                continue
            if (
                path.is_file()
                and len(rel.parts) == 1
                and path.suffix.lower() == ".json"
                and (path.name in ROOT_GENERATED_JSON_NAMES or path.name.startswith(ROOT_GENERATED_JSON_PREFIXES))
            ):
                blockers.append({"path": rel_posix, "reason": "generated_evidence_json_at_repo_root"})
                continue
            if (
                path.is_file()
                and path.suffix.lower() == ".json"
                and rel.parts[:2] == ("docs", "sample-evidence")
            ):
                warnings.append({"path": rel_posix, "reason": "sample_only_not_release_evidence"})

        return {
            "schema": "maine_family_law_llm.release_artifact_audit.v1",
            "status": "pass" if not blockers else "fail",
            "safe_to_package": not blockers,
            "production_legal_ga": False,
            "blockers": blockers,
            "warnings": warnings,
        }
