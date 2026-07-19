from __future__ import annotations


def test_bundled_fixture_retrieval_does_not_write_a_cache(monkeypatch) -> None:
    from maine_family_law_llm.fetch import SourceFetcher
    from maine_family_law_llm.workbench import build_fixture_chunks, retrieve_fixture_sources

    def fail_if_called(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("bundled fixture retrieval must not write a cache")

    monkeypatch.setattr(SourceFetcher, "_write_cache", fail_if_called)
    chunks = build_fixture_chunks()
    response = retrieve_fixture_sources("served family court papers")

    assert chunks
    assert response.results
