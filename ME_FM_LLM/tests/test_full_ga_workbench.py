from __future__ import annotations

import json
from pathlib import Path

from legal.ops import FullGAWorkbenchBuilder, build_full_ga_workbench

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def seed_complete_external_evidence(data_root: Path) -> None:
    write_json(
        data_root / "official_authority_store" / "source_manifest.json",
        [
            {"source_id": "live-statute-index", "source_class": "statute_title_index", "jurisdiction": "maine"},
            {"source_id": "live-statute-pdf", "source_class": "statute_pdf", "jurisdiction": "maine"},
            {"source_id": "live-rules", "source_class": "judicial_branch_rules", "jurisdiction": "maine"},
            {"source_id": "live-family-rules", "source_class": "family_division_rules", "jurisdiction": "maine"},
            {"source_id": "live-forms", "source_class": "court_forms_index", "jurisdiction": "maine"},
            {"source_id": "live-opinions", "source_class": "law_court_opinions_index", "jurisdiction": "maine"},
            {"source_id": "live-federal", "source_class": "federal_family_law", "jurisdiction": "federal"},
        ],
    )
    write_json(
        data_root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {"record_counts": {"statutes": 100, "rules": 25, "forms": 40, "opinions": 300}},
    )
    write_json(data_root / "embedding_store" / "retrieval_index_manifest.json", {"indexes": ["bm25", "vector", "hybrid"]})
    write_json(
        data_root / "eval_store" / "gold_eval_pack_manifest.json",
        {"attorney_reviewed_rows_total": 3000, "datasets": [{"name": "maine_rag_retrieval_gold", "attorney_reviewed_rows": 500}]},
    )
    write_json(
        data_root / "eval_store" / "release_metrics_evidence.json",
        {
            "metrics": [
                {"name": "retrieval_recall_at_20", "value": 0.96},
                {"name": "citation_existence", "value": 0.995},
                {"name": "citation_support", "value": 0.96},
                {"name": "quote_span_verification", "value": 0.98},
                {"name": "hallucination_rate", "value": 0.02},
                {"name": "filing_ready_false_pass_rate", "value": 0.0},
                {"name": "form_freshness_detection", "value": 0.995},
            ]
        },
    )
    write_json(
        data_root / "release_evidence" / "security_governance_packet.json",
        {
            "security_signoff_complete": True,
            "threat_model_complete": True,
            "privacy_impact_assessment_complete": True,
            "incident_response_plan_complete": True,
            "rollback_drill_complete": True,
        },
    )
    write_json(
        data_root / "release_evidence" / "pilot_evidence_packet.json",
        {
            "pilot_status": "passed",
            "no_data_leakage": True,
            "no_unsupported_filing_ready_exports": True,
            "attorney_signoff_present": True,
        },
    )
    write_json(
        data_root / "release_evidence" / "owner_signoffs.json",
        {
            "signoffs": [
                {"role": "security_owner", "approved": True},
                {"role": "legal_owner", "approved": True},
                {"role": "product_owner", "approved": True},
                {"role": "ops_owner", "approved": True},
            ]
        },
    )
    write_json(data_root / "release_evidence" / "rollback_package_manifest.json", {"rollback_package_ready": True})


def test_full_ga_workbench_blocks_empty_external_data(tmp_path):
    report = FullGAWorkbenchBuilder(ROOT, tmp_path / "empty_data_root").build(create_external_dirs=False).as_dict()
    assert report["status"] == "fail"
    assert report["ready_for_local_testing"] is True
    assert report["networked_source_ready"] is False
    assert report["production_legal_ready"] is False
    assert "networked_source_gate_not_passed" in report["blockers"]
    assert any(item["present"] is False for item in report["evidence_inventory"])


def test_full_ga_workbench_passes_with_complete_non_fixture_external_evidence(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_complete_external_evidence(data_root)
    report = FullGAWorkbenchBuilder(ROOT, data_root).build(create_external_dirs=False).as_dict()
    assert report["status"] == "pass"
    assert report["ready_for_local_testing"] is True
    assert report["networked_source_ready"] is True
    assert report["production_legal_ready"] is True
    assert all(item["fixture_marker_detected"] is False for item in report["evidence_inventory"])
    assert report["production_promotion_gate"]["status"] == "pass"


def test_full_ga_workbench_rejects_fixture_evidence(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_complete_external_evidence(data_root)
    metrics_path = data_root / "eval_store" / "release_metrics_evidence.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["note"] = "synthetic-only smoke result must stay blocked"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    report = build_full_ga_workbench(ROOT, data_root, create_external_dirs=False)
    assert report["status"] == "fail"
    assert report["production_legal_ready"] is False
    assert "fixture_marker_detected" in report["blockers"]


def test_full_ga_workbench_blocks_data_root_inside_repo():
    report = build_full_ga_workbench(ROOT, ROOT / "runtime" / "bad_ga_workbench_root", create_external_dirs=False)
    assert report["status"] == "fail"
    assert "data_root_inside_source_repo" in report["blockers"]
