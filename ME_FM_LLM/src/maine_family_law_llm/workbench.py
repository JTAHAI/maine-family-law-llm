"""Shared local fixture pipeline used by CLI and API."""

from __future__ import annotations

from pathlib import Path

from .chunk import chunk_document
from .fetch import SourceFetcher
from .index import load_index, save_index
from .normalize import normalize_fetch_result
from .retrieve import KeywordRetriever, RetrievalResponse
from .sources import DEFAULT_CACHE_DIR, DEFAULT_FIXTURES_DIR, DEFAULT_INDEX_PATH, load_seed_manifest


def build_fixture_chunks(*, cache_dir: str | Path = DEFAULT_CACHE_DIR) -> list[dict[str, object]]:
    entries = load_seed_manifest()
    fetcher = SourceFetcher(DEFAULT_FIXTURES_DIR, cache_dir, allow_live=False)
    chunks = []
    for entry in entries:
        result = fetcher.fetch(entry, fixtures=True, force=True)
        if not result.ok:
            continue
        normalized = normalize_fetch_result(result)
        chunks.extend(chunk_document(normalized))
    return [chunk.to_dict() for chunk in chunks]


def build_fixture_index(path: str | Path = DEFAULT_INDEX_PATH) -> Path:
    chunks = build_fixture_chunks()
    return save_index(path, [type("_ChunkProxy", (), {"to_dict": lambda self, payload=chunk: payload})() for chunk in chunks])


def get_fixture_retriever() -> KeywordRetriever:
    if Path(DEFAULT_INDEX_PATH).exists():
        chunks = load_index(DEFAULT_INDEX_PATH)
    else:
        chunks = build_fixture_chunks()
    return KeywordRetriever(chunks)


def retrieve_fixture_sources(query: str, *, limit: int = 5) -> RetrievalResponse:
    return get_fixture_retriever().search(query, limit=limit)
