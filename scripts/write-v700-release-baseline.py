#!/usr/bin/env python3
"""Create the non-Git v7 release identity and conservative scope baseline."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "dist" / "release" / "v7.0.0"
EVIDENCE_ROOT = RELEASE_ROOT / "evidence"

EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "eval_data",
    "eval_store",
    "indexes",
    "matter_data",
    "model_cache",
    "models",
    "node_modules",
    "runtime",
    "runtime_data",
    "screenshots",
    "tmp",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log"}
RELEASE_ROOT_FILES = {
    ".gitignore",
    "AGENTS.md",
    "LICENSE.md",
    "MANIFEST.in",
    "NOTICE.md",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
}
RELEASE_ROOT_PREFIXES = (
    "app/",
    "assets/",
    "configs/",
    "data/",
    "docs/",
    "legal/",
    "maine_family_law_llm/",
    "sample_question_bank/",
    "scripts/",
    "src/",
    "store/",
    "tests/",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _release_relevant(path: Path) -> bool:
    relative = _normalized(path)
    parts = set(path.relative_to(ROOT).parts[:-1])
    if parts.intersection(EXCLUDED_DIRS):
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    return relative in RELEASE_ROOT_FILES or relative.startswith(RELEASE_ROOT_PREFIXES)


def _git_probe() -> dict[str, Any]:
    command = ["git", "rev-parse", "--show-toplevel"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return {
            "identity_type": "SOURCE_TREE_IDENTITY_NON_GIT",
            "git_available": False,
            "reason": (completed.stderr or completed.stdout or "Git metadata unavailable").strip(),
        }
    return {
        "identity_type": "GIT",
        "git_available": True,
        "root": completed.stdout.strip(),
    }


def _read_version() -> dict[str, str]:
    namespace: dict[str, Any] = {}
    exec((ROOT / "src" / "maine_family_law_llm" / "version.py").read_text(encoding="utf-8"), namespace)
    return {
        "product_version": str(namespace.get("VERSION") or "unknown"),
        "package_version": str(namespace.get("PACKAGE_VERSION") or "unknown"),
    }


def _scope() -> dict[str, Any]:
    return json.loads((ROOT / "configs" / "v700_release_scope.json").read_text(encoding="utf-8"))


def main() -> int:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (path for path in ROOT.rglob("*") if path.is_file() and _release_relevant(path)),
        key=_normalized,
    )
    manifest = {
        "schema_version": "source_tree_manifest_v1",
        "identity_type": "SOURCE_TREE_IDENTITY_NON_GIT",
        "root_label": ROOT.name,
        "exclusion_policy": {
            "directories": sorted(EXCLUDED_DIRS),
            "suffixes": sorted(EXCLUDED_SUFFIXES),
            "notes": "Generated artifacts, runtime/matter data, authority/index/model/eval stores, caches, and temporary files are excluded.",
        },
        "files": [
            {"path": _normalized(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in files
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = EVIDENCE_ROOT / "source-tree-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    (EVIDENCE_ROOT / "source-tree-manifest.sha256").write_text(
        f"{manifest_sha}  source-tree-manifest.json\n", encoding="utf-8", newline="\n"
    )

    scope = _scope()
    scope_path = RELEASE_ROOT / "release-scope.json"
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    scope_path.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    versions = _read_version()
    baseline = {
        "schema_version": "v7_release_worktree_baseline_v1",
        "generated_at": _utc_now(),
        "source_identity": {
            **_git_probe(),
            "manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
            "manifest_sha256": manifest_sha,
            "file_count": len(files),
        },
        "versions": versions,
        "scope": {
            "public_feature_count": len(scope["public_features"]),
            "candidate_feature_count": len(scope["candidate_features"]),
            "hidden_feature_ids": [row["feature_id"] for row in scope["hidden_features"]],
        },
        "known_release_blockers_to_retest": [
            "final v7 MSIX is not yet built or isolated-install qualified",
            "WACK status is not yet recorded for the final v7 artifact",
            "Partner Center production signing is not performed locally",
        ],
    }
    (EVIDENCE_ROOT / "release-worktree-baseline.json").write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    scope_doc = ROOT / "docs" / "V7_RELEASE_SCOPE.md"
    scope_doc.write_text(
        "# v7.0.0 release scope\n\n"
        "The v7 release uses a smaller-verified-scope policy. No feature is public merely because source code or an API route exists. "
        "A feature moves from candidate to public only after production-UI, frozen-runtime, installed-package, privacy, review-status, and end-to-end evidence pass.\n\n"
        "## Current public scope\n\nThe public scope is limited to the 16 workflows listed in `configs/v700_release_scope.json`: launch, matter open, record import/inventory, deterministic parsing, OCR derivative creation, document privacy review, duplicate/change review, source-backed Maine research, exact official-source preview, citation/quote verification, drafting/revisions, review-required packets, the canonical filing gate, Local-only controls, and backup/restore.\n\n"
        "## Hidden scope\n\nSlices 21–31 remain hidden and unadvertised. Their backend data is preserved non-destructively; an explicit development-only override may expose them for engineering tests. Slices 32–44 are not part of this run. Timeline correction, claim-disposition, current guided forms, installed tracked-DOCX, command-center/snapshot, and missing-attachment coverage claims are also excluded because installed end-to-end proof is incomplete.\n\n"
        "## Canonical manifest\n\n`configs/v700_release_scope.json` is the source-controlled scope. Release tooling copies it to `dist/release/v7.0.0/release-scope.json`, which is the only generated input permitted for Store feature copy.\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": "pass", "manifest_sha256": manifest_sha, "file_count": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
