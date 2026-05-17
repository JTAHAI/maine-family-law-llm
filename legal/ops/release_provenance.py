from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ReleaseProvenanceReport:
    status: str
    project_root: str
    generated_at: str
    file_count: int
    total_bytes: int
    source_tree_hash: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    excluded_runtime_dirs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "source_tree_hash": self.source_tree_hash,
            "artifacts": list(self.artifacts),
            "excluded_runtime_dirs": list(self.excluded_runtime_dirs),
        }


class ReleaseProvenanceBuilder:
    """Build a deterministic source-file provenance inventory for release evidence."""

    excluded_parts = {".git", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "node_modules", "dist"}
    runtime_dirs = [
        "runtime",
        "uploads",
        "corpora",
        "vectorstores",
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "eval_store",
        "matter_store",
        "model_store",
        "model_registry",
        "audit_store",
    ]

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def build(self) -> ReleaseProvenanceReport:
        artifacts: list[dict[str, Any]] = []
        total = 0
        for path in sorted(self.project_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.project_root)
            if any(part in self.excluded_parts for part in rel.parts):
                continue
            digest = _sha256(path)
            size = path.stat().st_size
            total += size
            artifacts.append({"path": rel.as_posix(), "sha256": digest, "bytes": size})
        tree_basis = "\n".join(f"{item['path']} {item['sha256']} {item['bytes']}" for item in artifacts)
        tree_hash = hashlib.sha256(tree_basis.encode("utf-8")).hexdigest()
        return ReleaseProvenanceReport(
            status="pass",
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            file_count=len(artifacts),
            total_bytes=total,
            source_tree_hash=tree_hash,
            artifacts=artifacts,
            excluded_runtime_dirs=self.runtime_dirs,
        )

    def write(self, output_path: str | Path) -> ReleaseProvenanceReport:
        report = self.build()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report
