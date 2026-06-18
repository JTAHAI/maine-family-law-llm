from __future__ import annotations

import json
from pathlib import Path

from corpus_builder_support import build_fixture_case
from app.wizard_import_corpus import import_additional_corpus
from app.wizard_new_case import coerce_source_roots
from maine_family_law_llm.case_corpus_builder import discover_source_files
from maine_family_law_llm.case_workspace import load_case_summary, read_case_ingest_history, read_case_source_roots


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
    assert any((case_root / "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY" / "files").iterdir())
    assert any((case_root / "02_EXTERNAL_LEGAL_MATTER_RELEASE" / "files").iterdir())
    assert (case_root / "00_START_HERE" / "search.html").exists()


def test_source_root_coercion_preserves_order_and_dedupes_duplicates(tmp_path) -> None:
    first = tmp_path / "source_one"
    second = tmp_path / "source_two"
    roots = coerce_source_roots([first, second, Path(str(first)), Path(""), first])
    assert roots == [first, second]


def test_case_build_writes_source_roots_manifest(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    case_root = built["case_root"]
    source_root = built["source_root"]
    source_roots = read_case_source_roots(case_root)
    assert source_roots == [source_root]


def test_discover_source_files_accepts_direct_file_inputs(tmp_path) -> None:
    standalone = tmp_path / "standalone_notice.pdf"
    standalone.write_text("pdf placeholder", encoding="utf-8")
    discovered = discover_source_files([standalone])
    assert discovered == [standalone]


def test_import_additional_corpus_carries_forward_prior_source_roots(tmp_path) -> None:
    built = build_fixture_case(tmp_path, case_name="Persistent Matter")
    repo_root = built["repo_root"]
    original_case_root = built["case_root"]

    delta_root = tmp_path / "delta_source"
    delta_root.mkdir(parents=True, exist_ok=True)
    (delta_root / "new_school_update.txt").write_text(
        "New school records access update and attendance escalation.",
        encoding="utf-8",
    )

    expanded = import_additional_corpus(
        repo_root=repo_root,
        existing_case_root=original_case_root,
        source_roots=[delta_root],
        output_root=original_case_root.parent,
        case_name="Persistent Matter Expanded",
    )
    expanded_source_roots = read_case_source_roots(expanded.case_root)
    assert built["source_root"] in expanded_source_roots
    assert delta_root in expanded_source_roots

    search_index = json.loads((expanded.case_root / "04_INDEXES" / "search_index.json").read_text(encoding="utf-8"))
    source_paths = {row["source_path"] for row in search_index}
    assert any("2026-02-11_order.txt" in path for path in source_paths)
    assert any("new_school_update.txt" in path for path in source_paths)


def test_ingest_history_helpers_read_empty_history_until_recorded(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    assert read_case_ingest_history(built["case_root"]) == []


def test_case_summary_reports_missing_remembered_source_paths(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    case_root = built["case_root"]
    source_root = built["source_root"]
    source_root.rename(tmp_path / "fixture_source_corpus_moved")
    summary = load_case_summary(case_root)
    assert summary["source_root_count"] == 1
    assert summary["available_source_root_count"] == 0
    assert summary["missing_source_root_count"] == 1
