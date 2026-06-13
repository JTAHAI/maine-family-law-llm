from __future__ import annotations

from corpus_builder_support import build_fixture_case
from maine_family_law_llm.case_corpus_builder import LOCAL_ONLY_DEFAULT, NO_CLOUD_DEFAULT


def test_default_operation_is_local_only_and_no_cloud(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    assert LOCAL_ONLY_DEFAULT is True
    assert NO_CLOUD_DEFAULT is True
    assert built["proof"]["cloud_calls_made"] == 0
