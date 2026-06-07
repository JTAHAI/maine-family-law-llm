from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGING_EXCLUDE_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".mfl_work",
    "__pycache__",
    "dist",
    "node_modules",
    "build",
    ".eggs",
    ".proofs",
}

PRIVATE_OR_RUNTIME_DIRS = {
    "corpora",
    "runtime",
    "uploads",
    "vectorstores",
    "official_authority_store",
    "parsed_authority_store",
    "matter_store",
    "eval_store",
    "embedding_store",
    "audit_store",
    "model_registry",
    ".local_data",
}

PRIVATE_OR_RUNTIME_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".faiss",
    ".bin",
    ".pt",
    ".pth",
    ".safetensors",
    ".onnx",
    ".env",
    ".pyc",
}

PRIVATE_OR_RUNTIME_FILENAMES = {
    ".env",
    "client_secret.json",
    "id_rsa",
    "id_ed25519",
}


@dataclass(frozen=True)
class ReleaseFinding:
    path: str
    reason: str


@dataclass
class ReleaseManifest:
    """Generate a release manifest from actual repository checks.

    This does not certify legal readiness. It only checks that the source package is
    structurally safe to release and that runtime/private artifacts are not present.
    """

    project_root: Path | str = Path(".")
    release_name: str = "maine-family-law-llm"
    version: str = "1.8.0-pass17-pass18-authority-gold-data-product"
    exclude_dirs: set[str] = field(default_factory=lambda: set(PACKAGING_EXCLUDE_DIRS))
    deny_dirs: set[str] = field(default_factory=lambda: set(PRIVATE_OR_RUNTIME_DIRS))
    deny_suffixes: set[str] = field(default_factory=lambda: set(PRIVATE_OR_RUNTIME_SUFFIXES))
    deny_filenames: set[str] = field(default_factory=lambda: set(PRIVATE_OR_RUNTIME_FILENAMES))

    def _root(self) -> Path:
        return Path(self.project_root).resolve()

    def scan_release_tree(self) -> list[ReleaseFinding]:
        root = self._root()
        findings: list[ReleaseFinding] = []

        for path in root.rglob("*"):
            if path == root:
                continue

            rel = path.relative_to(root).as_posix()
            parts = set(path.relative_to(root).parts)

            excluded_dirs = sorted(parts & self.exclude_dirs)
            generated_metadata_dirs = sorted(part for part in parts if part.endswith(".egg-info"))
            if excluded_dirs or generated_metadata_dirs:
                # Dev/build caches are excluded from packages but are not treated as
                # private matter data. Skip their contents for stable local tests.
                continue

            blocked_dirs = sorted(parts & self.deny_dirs)
            if blocked_dirs:
                findings.append(
                    ReleaseFinding(path=rel, reason=f"blocked directory: {blocked_dirs[0]}")
                )
                continue

            if path.is_file():
                if path.name in self.deny_filenames:
                    findings.append(ReleaseFinding(path=rel, reason=f"blocked filename: {path.name}"))
                    continue

                if path.suffix.lower() in self.deny_suffixes:
                    findings.append(ReleaseFinding(path=rel, reason=f"blocked suffix: {path.suffix}"))

        return findings

    def generate(self) -> dict[str, Any]:
        findings = self.scan_release_tree()
        private_or_runtime_artifacts = [finding.__dict__ for finding in findings]

        return {
            "release_name": self.release_name,
            "version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "contains_private_data": bool(private_or_runtime_artifacts),
            "runtime_state_packaged": bool(private_or_runtime_artifacts),
            "private_or_runtime_artifacts": private_or_runtime_artifacts,
            "review_required_by_default": True,
            "filing_ready_export_default": "blocked",
            "canonical_stores_packaged": bool(private_or_runtime_artifacts),
            "data_boundary_status": "pass" if not private_or_runtime_artifacts else "fail",
            "legal_readiness": "authority_build_and_gold_eval_pack_gates_installed_but_not_release_ready_until_external_corpus_attorney_gold_metrics_security_audit_and_pilot_are_complete",
        }
