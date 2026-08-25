from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.authority_store.authority_layer import ParsedAuthorityIndexBuilder
from legal.evals.retrieval_smoke import RetrievalSmokeEvalRunner
from legal.production.retrieval_failure_triage import RetrievalFailureTriage
from legal.retrieval import RetrievalDocument, RetrievalPipeline
from legal.retrieval.index_builder import RetrievalIndexBuilder
from legal.verifiers import SourceAuthorityIndex, extract_citations


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _fixture_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    base = {
        "source_id": "snapshot-fixture",
        "source_hash": "hash-fixture",
        "jurisdiction": "maine",
        "freshness_status": "fresh",
        "parser_status": "parsed",
        "source_span": {"start_offset": 0, "end_offset": 100},
        "source_url_or_path": "https://official.example/fixture",
    }
    _write_jsonl(
        parsed / "statutes" / "statute_title_indexes.jsonl",
        [
            {
                **base,
                "record_id": "statute-19a-1653",
                "source_class": "statute_title_index",
                "authority_kind": "statute_section_reference",
                "title": "Parental rights and responsibilities; best interest of the child",
                "citation": "19-A M.R.S. § 1653",
                "text": "Maine custody and parental rights are decided using best interest factors, primary residence, and contact.",
                "section_number": "1653",
                "issue_labels": ["parental_rights_responsibilities", "primary_residence"],
            }
        ],
    )
    _write_jsonl(
        parsed / "rules" / "rules_index.jsonl",
        [
            {
                **base,
                "record_id": "rule-mrcp-120",
                "source_class": "court_rules_index",
                "authority_kind": "court_rule_reference",
                "title": "Family matter findings order",
                "citation": "M.R. Civ. P. 120",
                "text": "Family matter findings must be sufficient for appellate review.",
                "rule_number": "120",
                "issue_labels": ["Rule_52_findings"],
            }
        ],
    )
    _write_jsonl(
        parsed / "forms" / "forms_index.jsonl",
        [
            {
                **base,
                "record_id": "form-fm-002",
                "source_class": "court_forms_index",
                "authority_kind": "court_form_reference",
                "title": "Family Matter Summary Sheet",
                "citation": "FM-002",
                "form_id": "FM-002",
                "version_date": "2026-01-01",
                "text": "Official Maine Judicial Branch form for family matters. Depends on M.R. Civ. P. 120.",
                "issue_labels": ["divorce"],
            }
        ],
    )
    _write_jsonl(
        parsed / "opinions" / "opinion_index.jsonl",
        [
            {
                **base,
                "record_id": "case-2026-me-1",
                "source_class": "law_court_opinion_index",
                "authority_kind": "law_court_opinion_reference",
                "title": "Test v. Test",
                "citation": "2026 ME 1",
                "text": "The Law Court applied 19-A M.R.S. § 1653 and M.R. Civ. P. 120 in a custody appeal.",
                "issue_labels": ["parental_rights_responsibilities", "appeal_preservation"],
            }
        ],
    )
    return data_root


def test_pass22_builds_citation_index_source_cards_and_authority_graph(tmp_path):
    data_root = _fixture_data_root(tmp_path)

    report = ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)

    assert report["status"] == "pass"
    assert report["citation_index_count"] >= 4
    assert report["authority_graph_edge_count"] >= 2
    index_rows = json.loads((data_root / "authority_layer" / "citation_index.json").read_text(encoding="utf-8"))
    index = SourceAuthorityIndex.from_rows(index_rows)
    real = index.resolve(extract_citations("19-A M.R.S. § 1653")[0])
    fake = index.resolve(extract_citations("19-A M.R.S. § 9999")[0])
    assert real.status == "found"
    assert real.source_id == "statute-19a-1653"
    assert fake.status == "not_found"
    graph = json.loads((data_root / "authority_layer" / "authority_graph.json").read_text(encoding="utf-8"))
    assert any(edge["relation"] == "case_cites_statute" for edge in graph["case-2026-me-1"])
    cards = [json.loads(line) for line in (data_root / "authority_layer" / "source_cards.jsonl").read_text(encoding="utf-8").splitlines()]
    case_card = next(card for card in cards if card["source_id"] == "case-2026-me-1")
    assert case_card["negative_treatment_status"] == "negative_treatment_unknown"


def test_pass23_builds_external_retrieval_indexes_and_lookup_artifacts(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)

    report = RetrievalIndexBuilder(data_root=data_root, repo_root=Path.cwd()).build()

    assert report.status == "pass"
    assert report.document_count == 4
    assert (data_root / "embedding_store" / "bm25" / "documents.jsonl").exists()
    assert (data_root / "embedding_store" / "vector" / "vectors.jsonl").exists()
    assert (data_root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl").exists()
    exact = json.loads((data_root / "embedding_store" / "hybrid" / "exact_citation_lookup.json").read_text(encoding="utf-8"))
    assert exact["19-A M.R.S. § 1653"] == "statute-19a-1653"
    assert report.outputs["index_manifest"].startswith(str(data_root))

    documents = RetrievalIndexBuilder(data_root=data_root).load_documents()
    pipeline = RetrievalPipeline(documents)
    response = pipeline.retrieve("FM-002", top_k=1)
    assert response["retrieved_sources"][0]["source_id"] == "form-fm-002"


def test_direct_statute_pinpoint_and_retrieval_card_preserve_exact_provenance(tmp_path):
    data_root = tmp_path / "external_data"
    text = "19-A M.R.S. § 1653. 1. Purpose text. 3. Best interest of child."
    _write_jsonl(
        data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl",
        [
            {
                "record_id": "statute-19a-1653",
                "source_id": "snapshot-statute",
                "source_hash": "a" * 64,
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": len(text)},
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
                "title": "Parental rights and responsibilities",
                "citation": "19-A M.R.S. § 1653",
                "text": text,
                "subsections": ["1. Purpose text.", "3. Best interest of child."],
            }
        ],
    )

    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    index_rows = json.loads((data_root / "authority_layer" / "citation_index.json").read_text(encoding="utf-8"))
    resolution = SourceAuthorityIndex.from_rows(index_rows).resolve(
        extract_citations("19-A M.R.S. § 1653(3)")[0]
    )
    assert resolution.status == "found"
    assert resolution.metadata["pinpoint"] == "19-A M.R.S. § 1653(3)"
    assert text[resolution.metadata["source_span"]["start_offset"] : resolution.metadata["source_span"]["end_offset"]] == "3. Best interest of child."

    RetrievalIndexBuilder(data_root=data_root).build()
    cards = [
        json.loads(line)
        for line in (data_root / "embedding_store" / "hybrid" / "source_cards.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert cards[0]["hash_value"] == "a" * 64
    assert cards[0]["start_offset"] == 0
    assert cards[0]["end_offset"] == len(text)
    exact = json.loads((data_root / "embedding_store" / "hybrid" / "exact_citation_lookup.json").read_text(encoding="utf-8"))
    assert exact["19-A M.R.S. § 1653(3)"] == "statute-19a-1653"


def test_pinpoint_index_supports_nested_statutes_rules_opinions_pages_and_form_revisions(tmp_path):
    data_root = tmp_path / "external_data"
    statute_text = "19-A M.R.S. § 1653. 3. Best interest. A. Safety factor."
    rule_text = "M.R. Civ. P. 4. C. Service. 1. Personal service."
    opinion_text = "2026 ME 1\n4. The exact paragraph.\nPage 2 exact text."
    _write_jsonl(
        data_root / "parsed_authority_store" / "mixed.jsonl",
        [
            {
                "record_id": "statute", "source_id": "statute-snapshot", "source_class": "statute_section",
                "authority_kind": "statute_section", "jurisdiction": "maine", "freshness_status": "fresh",
                "citation": "19-A M.R.S. § 1653", "title": "Statute", "text": statute_text,
                "source_span": {"start_offset": 0, "end_offset": len(statute_text)},
                "subsections": [{"label": "3", "text": "3. Best interest.", "children": [{"label": "A", "text": "A. Safety factor."}]}],
            },
            {
                "record_id": "rule", "source_id": "rule-snapshot", "source_class": "court_rule",
                "authority_kind": "court_rule", "jurisdiction": "maine", "freshness_status": "fresh",
                "citation": "M.R. Civ. P. 4", "title": "Rule", "text": rule_text,
                "source_span": {"start_offset": 0, "end_offset": len(rule_text)},
                "subdivisions": [{"label": "C", "text": "C. Service.", "children": [{"label": "1", "text": "1. Personal service."}]}],
            },
            {
                "record_id": "opinion", "source_id": "opinion-snapshot", "source_class": "law_court_opinion",
                "authority_kind": "law_court_opinion", "jurisdiction": "maine", "freshness_status": "fresh",
                "citation": "2026 ME 1", "title": "Opinion", "text": opinion_text,
                "source_span": {"start_offset": 0, "end_offset": len(opinion_text)},
                "paragraphs": [{"label": "4", "text": "4. The exact paragraph."}],
                "page_spans": [{"page": 2, "text": "Page 2 exact text."}],
            },
            {
                "record_id": "form", "source_id": "form-snapshot", "source_class": "court_form",
                "authority_kind": "court_form", "jurisdiction": "maine", "freshness_status": "fresh",
                "citation": "FM-002", "title": "Form", "text": "FM-002 current form",
                "source_span": {"start_offset": 0, "end_offset": 19}, "version_date": "2026-01-01",
            },
        ],
    )
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    index = SourceAuthorityIndex.from_rows(json.loads((data_root / "authority_layer" / "citation_index.json").read_text(encoding="utf-8")))

    nested = index.resolve(extract_citations("19-A M.R.S. § 1653(3)(A)")[0])
    rule = index.resolve(extract_citations("M.R. Civ. P. 4(C)(1)")[0])
    paragraph = index.resolve(extract_citations("2026 ME 1, ¶ 4")[0])
    form = index.resolve(extract_citations("FM-002")[0])

    assert nested.metadata["pinpoint_type"] == "statute_paragraph"
    assert rule.metadata["pinpoint_type"] == "rule_subdivision"
    assert paragraph.metadata["requested_pinpoint_matched"] is True
    assert paragraph.metadata["pinpoint_type"] == "opinion_paragraph"
    assert form.metadata["form_revision"] == "2026-01-01"


def test_pass24_runs_measured_retrieval_smoke_eval(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    RetrievalIndexBuilder(data_root=data_root).build()

    report = RetrievalSmokeEvalRunner(data_root=data_root).run(write_report=True)

    assert report.status == "pass"
    assert report.metrics["recall_at_20"] >= 0.9
    assert report.metrics["mrr"] > 0
    assert (data_root / "eval_store" / "retrieval_smoke_eval.json").exists()


def test_pass24_retrieval_smoke_caps_source_derived_cases_and_writes_progress(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    RetrievalIndexBuilder(data_root=data_root).build()

    report = RetrievalSmokeEvalRunner(data_root=data_root).run(
        write_report=True,
        min_case_count=2,
        max_case_count=2,
        progress_interval=1,
    )

    assert report.status == "pass"
    assert report.case_count == 2
    assert report.thresholds["max_case_count"] == 2
    progress = json.loads((data_root / "retrieval_smoke_progress.json").read_text(encoding="utf-8"))
    assert progress["completed_cases"] == 2
    assert progress["total_cases"] == 2
    assert (data_root / "retrieval_smoke_report.json").exists()


def test_source_derived_smoke_treats_duplicate_citation_rows_as_equivalent() -> None:
    documents = [
        RetrievalDocument(
            source_id=source_id,
            document_id=source_id,
            title=f"Rule 120 copy {source_id}",
            text="Post-judgment relief.",
            citation="M.R. Civ. P. 120",
            source_class="court_rules_index",
        )
        for source_id in ("rule-120-a", "rule-120-b")
    ]

    cases = RetrievalSmokeEvalRunner._build_cases(documents, max_case_count=10)

    assert len(cases) == 1
    assert cases[0].relevant_source_ids == {"rule-120-a", "rule-120-b"}


def test_admitted_exact_citation_precedes_substring_false_positives() -> None:
    documents = [
        RetrievalDocument(
            source_id="rule-1",
            document_id="rule-1",
            title="Rule 1 - Scope",
            text="Scope of rules.",
            citation="M.R. Civ. P. 1",
            source_class="court_rule",
            authority_status="verified_official_maine",
        ),
        RetrievalDocument(
            source_id="rule-10",
            document_id="rule-10",
            title="Rule 10 - Pleadings",
            text="M.R. Civ. P. 10 governs pleadings.",
            citation="M.R. Civ. P. 10",
            source_class="court_rule",
            authority_status="verified_official_maine",
        ),
    ]
    authority = SourceAuthorityIndex()
    authority.add_rule("M.R. Civ. P. 1", "rule-1")

    response = RetrievalPipeline(documents, authority_index=authority).retrieve("M.R. Civ. P. 1", top_k=2)

    assert response["retrieved_sources"][0]["source_id"] == "rule-1"
    assert response["retrieved_sources"][0]["method"] == "admitted_exact_citation"


def test_pass25_triages_retrieval_failures_into_fix_tickets(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    RetrievalIndexBuilder(data_root=data_root).build()
    eval_root = data_root / "eval_store"
    eval_root.mkdir(parents=True, exist_ok=True)
    (eval_root / "retrieval_smoke_eval.json").write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "query": "19-A M.R.S. § 9999",
                        "expected_source_ids": ["statute-missing"],
                        "retrieved_source_ids": [],
                        "expected_source_class": "statute_title_index",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = RetrievalFailureTriage(data_root=data_root).run(write_report=True)

    assert report["status"] == "needs_retrieval_fixes"
    assert report["clusters"] == {"missed_exact_citation": 1}
    assert report["tickets"][0]["remediation"].startswith("add or repair exact citation")
    assert (eval_root / "retrieval_failure_tickets.jsonl").exists()


def test_pass24_retrieval_smoke_blocks_when_case_threshold_not_met(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    RetrievalIndexBuilder(data_root=data_root).build()

    report = RetrievalSmokeEvalRunner(data_root=data_root).run(write_report=True, min_case_count=99)

    assert report.status == "blocked"
    assert any(blocker["code"] == "insufficient_case_count" for blocker in report.blockers)
    payload = json.loads((data_root / "eval_store" / "retrieval_smoke_eval.json").read_text(encoding="utf-8"))
    assert payload["thresholds"]["min_case_count"] == 99
    assert payload["thresholds"]["basis"] == "source-derived smoke cases; not attorney-reviewed GA gold"


def test_pass24_retrieval_smoke_cli_accepts_release_thresholds(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    RetrievalIndexBuilder(data_root=data_root).build()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-retrieval-smoke-eval.py",
            "--data-root",
            str(data_root),
            "--min-case-count",
            "99",
            "--min-recall-at-20",
            "0.95",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["thresholds"]["min_recall_at_20"] == 0.95
    assert any(blocker["code"] == "insufficient_case_count" for blocker in payload["blockers"])
