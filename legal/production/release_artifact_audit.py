"""Release tree artifact hygiene audit.

The source repository must remain a clean source package. Evidence JSON, SBOMs,
release locks, smoke reports, local reports, corpora, vector indexes, model files,
and matter data are generated artifacts and must be written to explicit output
paths or external data/evidence roots instead of living at the repo root.
"""
from __future__ import annotations

from dataclasses import dataclass
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
            if path.is_dir() and path.name in PROHIBITED_RELEASE_DIR_NAMES:
                blockers.append({"path": rel_posix, "reason": "external_artifact_directory_in_repo"})
                continue
            if path.is_file() and path.suffix.lower() in PROHIBITED_SUFFIXES:
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
