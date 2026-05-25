from __future__ import annotations

import pytest

from maine_family_law_llm.retrieve import KeywordRetriever
from maine_family_law_llm.workbench import build_fixture_chunks


def test_keyword_retrieval_finds_fixture_sources() -> None:
    response = KeywordRetriever(build_fixture_chunks()).search("parental rights")

    assert response.ok is True
    assert response.results
    assert response.results[0].snippet
    assert response.results[0].metadata["official"] is True


def test_official_sources_rank_above_secondary_when_both_match() -> None:
    response = KeywordRetriever(build_fixture_chunks()).search("parental rights child support")

    assert response.results[0].metadata["official"] is True


def test_empty_query_rejected_and_no_results_are_clear() -> None:
    retriever = KeywordRetriever(build_fixture_chunks())
    with pytest.raises(ValueError):
        retriever.search(" ")

    response = retriever.search("zzzz-nothing-matches")
    assert response.failure_class == "no_sources_found"
    assert response.recovery_hint
