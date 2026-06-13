from __future__ import annotations

import json

from corpus_builder_support import REPO_ROOT, build_fixture_case
from maine_family_law_llm.case_corpus_builder import bootstrap_repository
from maine_family_law_llm.question_bank import ROLE_QUESTION_MINIMUMS


def test_builtin_question_bank_meets_minimums() -> None:
    assets = bootstrap_repository(REPO_ROOT)
    question_bank_path = assets["question_bank_path"]
    counts = {key: 0 for key in ROLE_QUESTION_MINIMUMS}
    for line in question_bank_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        counts[row["role"]] += 1
    assert counts == ROLE_QUESTION_MINIMUMS


def test_question_coverage_matrix_is_built(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    coverage_root = built["case_root"] / "04_INDEXES"
    assert (coverage_root / "QUESTION_COVERAGE_MATRIX.csv").exists()
    assert (coverage_root / "QUESTION_COVERAGE_MATRIX.html").exists()
    assert (coverage_root / "QUESTION_COVERAGE_MATRIX.jsonl").exists()
    assert built["proof"]["coverage_green"] > 0
