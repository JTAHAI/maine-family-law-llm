from pathlib import Path
import json

from legal.ops import NetworkedSourceGateAuditor, run_networked_source_gate

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def seed_networked_data_root(data_root: Path):
    write_json(
        data_root / "official_authority_store" / "source_manifest.json",
        [
            {"source_id": "src-statute-index", "source_class": "statute_title_index", "jurisdiction": "maine"},
            {"source_id": "src-statute-pdf", "source_class": "statute_pdf", "jurisdiction": "maine"},
            {"source_id": "src-rules", "source_class": "judicial_branch_rules", "jurisdiction": "maine"},
            {"source_id": "src-family-rules", "source_class": "family_division_rules", "jurisdiction": "maine"},
            {"source_id": "src-forms", "source_class": "court_forms_index", "jurisdiction": "maine"},
            {"source_id": "src-opinions", "source_class": "law_court_opinions_index", "jurisdiction": "maine"},
            {"source_id": "src-federal", "source_class": "federal_family_law", "jurisdiction": "federal"},
        ],
    )
    write_json(
        data_root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {"record_counts": {"statutes": 2, "rules": 2, "forms": 2, "opinions": 2}},
    )
    write_json(
        data_root / "embedding_store" / "retrieval_index_manifest.json",
        {"indexes": ["bm25", "vector", "hybrid"]},
    )
    write_json(
        data_root / "eval_store" / "gold_eval_pack_manifest.json",
        {"attorney_reviewed_rows_total": 10, "datasets": []},
    )
    write_json(
        data_root / "eval_store" / "release_metrics_evidence.json",
        {
            "metrics": [
                {"name": "retrieval_recall_at_20", "value": 0.96},
                {"name": "citation_existence", "value": 0.99},
                {"name": "citation_support", "value": 0.95},
                {"name": "quote_span_verification", "value": 0.97},
                {"name": "hallucination_rate", "value": 0.02},
                {"name": "filing_ready_false_pass_rate", "value": 0.0},
                {"name": "form_freshness_detection", "value": 0.99},
            ]
        },
    )


def test_networked_source_gate_fails_cleanly_before_external_data_exists(tmp_path):
    report = NetworkedSourceGateAuditor(ROOT, tmp_path / "empty_data_root").audit().as_dict()
    assert report["status"] == "fail"
    assert report["networked_source_ready"] is False
    assert "missing_required_external_file" in report["blockers"]
    assert report["production_legal_ready"] is False


def test_networked_source_gate_passes_for_non_fixture_external_evidence(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_networked_data_root(data_root)
    report = NetworkedSourceGateAuditor(ROOT, data_root).audit().as_dict()
    assert report["status"] == "pass"
    assert report["networked_source_ready"] is True
    assert report["production_legal_ready"] is True
    assert report["source_class_counts"]["court_forms_index"] == 1
    assert report["gold_eval_rows_total"] == 10


def test_networked_source_gate_rejects_fixture_markers(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_networked_data_root(data_root)
    release_metrics = data_root / "eval_store" / "release_metrics_evidence.json"
    data = json.loads(release_metrics.read_text(encoding="utf-8"))
    data["note"] = "offline-smoke fixture should not pass"
    release_metrics.write_text(json.dumps(data), encoding="utf-8")
    report = run_networked_source_gate(ROOT, data_root)
    assert report["status"] == "fail"
    assert "fixture_marker_detected" in report["blockers"]



def seed_networked_data_root_with_actual_manifest_names(data_root: Path):
    write_json(
        data_root / "official_authority_store" / "source_manifest.json",
        [
            {"source_id": "src-statute-index", "source_class": "statute_title_index", "jurisdiction": "maine"},
            {"source_id": "src-statute-pdf", "source_class": "statute_title_pdf", "jurisdiction": "maine"},
            {"source_id": "src-rules", "source_class": "court_rules_index", "jurisdiction": "maine"},
            {"source_id": "src-policy", "source_class": "court_policy_index", "jurisdiction": "maine"},
            {"source_id": "src-forms", "source_class": "court_forms_index", "jurisdiction": "maine"},
            {"source_id": "src-opinions", "source_class": "law_court_opinion_index", "jurisdiction": "maine"},
            {"source_id": "src-federal", "source_class": "federal_family_law", "jurisdiction": "federal"},
        ],
    )
    write_json(
        data_root / "parsed_authority_store" / "parsed_manifest.json",
        {
            "counts_by_collection": {
                "statutes/statute_title_indexes.jsonl": 2,
                "rules/rules_index.jsonl": 2,
                "forms/forms_index.jsonl": 2,
                "opinions/opinion_index.jsonl": 2,
            }
        },
    )
    write_json(
        data_root / "embedding_store" / "index_manifest.json",
        {
            "outputs": {
                "bm25_documents": str(data_root / "embedding_store" / "bm25" / "documents.jsonl"),
                "vector_embeddings": str(data_root / "embedding_store" / "vector" / "vectors.jsonl"),
                "hybrid_documents": str(data_root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"),
            }
        },
    )
    write_json(
        data_root / "eval_store" / "gold_eval_pack_manifest.json",
        {"attorney_reviewed_rows_total": 10, "datasets": []},
    )
    write_json(
        data_root / "eval_store" / "release_metrics_evidence.json",
        {
            "metrics": {
                "retrieval_recall_at_20": {"value": 0.96},
                "citation_existence": {"value": 0.99},
                "citation_support": {"value": 0.95},
                "quote_span_verification": {"value": 0.97},
                "hallucination_rate": {"value": 0.02},
                "filing_ready_false_pass_rate": {"value": 0.0},
                "form_freshness_detection": {"value": 0.99},
            }
        },
    )


def test_networked_source_gate_accepts_actual_source_classes_and_legacy_manifest_names(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_networked_data_root_with_actual_manifest_names(data_root)
    report = NetworkedSourceGateAuditor(ROOT, data_root).audit().as_dict()
    assert report["status"] == "pass"
    assert report["source_class_counts"]["statute_title_pdf"] == 1
    assert report["source_class_counts"]["court_rules_index"] == 1
    assert report["source_class_counts"]["court_policy_index"] == 1
    assert report["source_class_counts"]["law_court_opinion_index"] == 1
    assert report["parsed_record_counts"] == {"forms": 2, "opinions": 2, "rules": 2, "statutes": 2}
    assert report["retrieval_indexes_present"] == ["bm25", "hybrid", "vector"]
    assert any(finding["check"] == "required_external_file_alternate" for finding in report["findings"])
