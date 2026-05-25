from __future__ import annotations

from maine_family_law_llm.fetch import SourceFetcher
from maine_family_law_llm.normalize import normalize_fetch_result
from maine_family_law_llm.sources import DEFAULT_FIXTURES_DIR, load_seed_manifest


def test_fixture_fetch_works_offline_and_preserves_metadata(tmp_path) -> None:
    entry = load_seed_manifest()[0]
    result = SourceFetcher(DEFAULT_FIXTURES_DIR, tmp_path).fetch(entry, fixtures=True)

    assert result.ok is True
    assert result.metadata["source_id"] == entry.id
    assert result.metadata["url"] == entry.url
    assert result.metadata["retrieved_at"]
    assert result.raw_path


def test_normalized_text_preserves_title_source_id_and_url(tmp_path) -> None:
    entry = load_seed_manifest()[0]
    result = SourceFetcher(DEFAULT_FIXTURES_DIR, tmp_path).fetch(entry, fixtures=True)
    normalized = normalize_fetch_result(result)

    assert entry.title in normalized.text
    assert entry.id in normalized.text
    assert entry.url in normalized.text
    assert "Chapter 55" in normalized.text


def test_failed_fetch_has_failure_class_and_recovery_hint(tmp_path) -> None:
    entry = load_seed_manifest()[0]
    fetcher = SourceFetcher(tmp_path / "missing-fixtures", tmp_path)
    result = fetcher.fetch(entry, fixtures=True)

    assert result.ok is False
    assert result.failure_class == "fixture_missing"
    assert result.recovery_hint
