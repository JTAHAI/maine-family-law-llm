"""Convenience helpers for bundled safe fixture and source paths."""

from __future__ import annotations

from pathlib import Path

from .source_manifest import SourceManifestEntry, load_manifest, validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "data" / "sources" / "manifest.seed.json"
DEFAULT_FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"
DEFAULT_CACHE_DIR = REPO_ROOT / ".mfl_work" / "cache"
DEFAULT_INDEX_PATH = REPO_ROOT / ".mfl_work" / "index" / "fixture_index.json"


def load_seed_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> list[SourceManifestEntry]:
    return validate_manifest(load_manifest(path))


def get_source(entries: list[SourceManifestEntry], source_id: str) -> SourceManifestEntry | None:
    for entry in entries:
        if entry.id == source_id:
            return entry
    return None
