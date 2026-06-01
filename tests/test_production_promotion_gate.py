from __future__ import annotations

import json
from pathlib import Path

from legal.ops import ProductionPromotionGateAuditor, run_production_promotion_gate

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def seed_external_production_evidence(data_root: Path) -> None:
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
    write_json(
        data_root / "embedding_store" / "retrieval_index_manifest.json",
        {"indexes": ["bm25", "vector", "hybrid"]},
    )
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
    write_json(
        data_root / "release_evidence" / "rollback_package_manifest.json",
        {"rollback_package_ready": True, "rollback_drill_id": "drill-2026-05-16"},
    )


def test_production_promotion_gate_fails_cleanly_without_external_evidence(tmp_path):
    report = ProductionPromotionGateAuditor(ROOT, tmp_path / "empty_data_root").audit().as_dict()
    assert report["status"] == "fail"
    assert report["production_legal_ready"] is False
    assert report["promotion_locked"] is True
    assert "networked_source_gate_not_passed" in report["blockers"]
    assert "missing_required_external_file" in report["blockers"]


def test_production_promotion_gate_passes_with_complete_non_fixture_evidence(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_external_production_evidence(data_root)
    report = ProductionPromotionGateAuditor(ROOT, data_root).audit().as_dict()
    assert report["status"] == "pass"
    assert report["production_legal_ready"] is True
    assert report["promotion_locked"] is False
    assert report["attorney_reviewed_rows_total"] == 3000
    assert set(report["owner_signoff_roles_present"]) == {"security_owner", "legal_owner", "product_owner", "ops_owner"}
    assert report["metric_results"]["retrieval_recall_at_20"]["status"] == "pass"


def test_production_promotion_gate_blocks_low_metric(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_external_production_evidence(data_root)
    metrics_path = data_root / "eval_store" / "release_metrics_evidence.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["metrics"][0]["value"] = 0.90
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    report = run_production_promotion_gate(ROOT, data_root)
    assert report["status"] == "fail"
    assert "metric_threshold_not_met" in report["blockers"]
    assert report["metric_results"]["retrieval_recall_at_20"]["status"] == "fail"


def test_production_promotion_gate_rejects_fixture_markers(tmp_path):
    data_root = tmp_path / "ME_FM_LLM_data"
    seed_external_production_evidence(data_root)
    signoff_path = data_root / "release_evidence" / "owner_signoffs.json"
    signoffs = json.loads(signoff_path.read_text(encoding="utf-8"))
    signoffs["note"] = "placeholder approval must not pass"
    signoff_path.write_text(json.dumps(signoffs), encoding="utf-8")
    report = ProductionPromotionGateAuditor(ROOT, data_root).audit().as_dict()
    assert report["status"] == "fail"
    assert "fixture_marker_detected" in report["blockers"]
