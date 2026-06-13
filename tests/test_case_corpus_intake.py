from __future__ import annotations

import json

from corpus_builder_support import build_fixture_case


def test_case_build_stays_under_selected_output_root_and_indexes_problem_files(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    case_root = built["case_root"]
    output_root = built["output_root"]
    assert str(case_root).startswith(str(output_root))
    problem_files = json.loads((case_root / "14_QUARANTINE_UNREADABLE_UNSUPPORTED" / "problem_files.json").read_text(encoding="utf-8"))
    assert any(row["reason"] == "unsupported" for row in problem_files)


def test_external_release_and_private_master_both_exist(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    case_root = built["case_root"]
    assert (case_root / "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY" / "private_forensic_master.jsonl").exists()
    assert (case_root / "02_EXTERNAL_LEGAL_MATTER_RELEASE" / "external_legal_matter_release.jsonl").exists()
