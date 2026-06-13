from __future__ import annotations

from corpus_builder_support import build_fixture_case
from maine_family_law_llm.case_corpus_builder import answer_case_question


def test_grounded_answer_cites_evidence_when_records_exist(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    answer = answer_case_question(built["case_root"], "What does the corpus show about school attendance and records access?")
    assert answer["direct_answer"].startswith("The corpus shows")
    assert answer["evidence_relied_on"]
    assert answer["evidence_ids_hashes_packet_paths"]


def test_not_found_answer_fails_closed(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    answer = answer_case_question(built["case_root"], "Tell me about an unrelated space alien incident")
    assert answer["direct_answer"] == "not found in the indexed corpus."
