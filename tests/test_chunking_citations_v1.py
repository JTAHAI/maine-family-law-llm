from __future__ import annotations

from maine_family_law_llm.chunk import chunk_document
from maine_family_law_llm.cite import render_citation_appendix
from maine_family_law_llm.fetch import SourceFetcher
from maine_family_law_llm.normalize import normalize_fetch_result
from maine_family_law_llm.sources import DEFAULT_FIXTURES_DIR, load_seed_manifest


def _chunks(tmp_path):
    entry = load_seed_manifest()[0]
    result = SourceFetcher(DEFAULT_FIXTURES_DIR, tmp_path).fetch(entry, fixtures=True)
    return chunk_document(normalize_fetch_result(result))


def test_chunks_preserve_source_metadata_and_nonempty_text(tmp_path) -> None:
    chunks = _chunks(tmp_path)

    assert chunks
    assert all(chunk.source_id for chunk in chunks)
    assert all(chunk.citation_hint for chunk in chunks)
    assert all(chunk.effective_date for chunk in chunks)
    assert all(chunk.version_label for chunk in chunks)
    assert all(chunk.text.strip() for chunk in chunks)


def test_stable_chunk_ids_repeat_on_same_fixture(tmp_path) -> None:
    first = [chunk.chunk_id for chunk in _chunks(tmp_path / "a")]
    second = [chunk.chunk_id for chunk in _chunks(tmp_path / "b")]

    assert first == second


def test_citation_appendix_renders_url_title_source_type() -> None:
    chunk = _chunks(__import__("tempfile").TemporaryDirectory().name)[0]
    appendix = render_citation_appendix([chunk])

    assert chunk.title in appendix
    assert chunk.url in appendix
    assert chunk.source_type in appendix
