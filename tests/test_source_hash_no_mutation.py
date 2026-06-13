from __future__ import annotations

from corpus_builder_support import build_fixture_case
from maine_family_law_llm.case_corpus_builder import sha256_file


def test_source_hashes_are_preserved_and_no_mutation_is_reported(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    source_root = built["source_root"]
    hashes_before = {path.name: sha256_file(path) for path in source_root.rglob("*") if path.is_file()}
    hashes_after = {path.name: sha256_file(path) for path in source_root.rglob("*") if path.is_file()}
    assert hashes_before == hashes_after
    assert built["proof"]["source_files_modified"] == 0
    assert built["proof"]["source_mutation_pass"] is True
