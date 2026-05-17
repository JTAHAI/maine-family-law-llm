from __future__ import annotations

import json
from pathlib import Path

from legal.authority_store.authority_layer import ParsedAuthorityIndexBuilder
from legal.evals.retrieval_smoke import RetrievalSmokeEvalRunner
from legal.production.retrieval_failure_triage import RetrievalFailureTriage
from legal.retrieval import RetrievalPipeline
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


def test_pass24_runs_measured_retrieval_smoke_eval(tmp_path):
    data_root = _fixture_data_root(tmp_path)
    ParsedAuthorityIndexBuilder(data_root=data_root).build(write=True)
    RetrievalIndexBuilder(data_root=data_root).build()

    report = RetrievalSmokeEvalRunner(data_root=data_root).run(write_report=True)

    assert report.status == "pass"
    assert report.metrics["recall_at_20"] >= 0.9
    assert report.metrics["mrr"] > 0
    assert (data_root / "eval_store" / "retrieval_smoke_eval.json").exists()


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
