from __future__ import annotations

import hashlib
import json
from pathlib import Path

from legal.evals import (
    GoldAnnotationQueueAuditor,
    GoldAnnotationQueueBuilder,
    GoldEvalPackManifestBuilder,
    ReleaseMetricsEvidenceBuilder,
)


def _manifest(tmp_path: Path) -> Path:
    snapshot = tmp_path / "official_authority_store" / "source-1.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("source text", encoding="utf-8")
    manifest_path = tmp_path / "official_authority_store" / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "source_id": "source-1",
                    "source_class": "statute_title_index",
                    "jurisdiction": "maine",
                    "hash": hashlib.sha256(b"source text").hexdigest(),
                    "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
                    "snapshot_path": str(snapshot),
                    "parser_status": "parsed",
                    "freshness_status": "known_extracted_timestamp",
                }
            ]
        ),
        encoding="utf-8",
    )
    return manifest_path


def _policy() -> dict:
    return {
        "annotation_queue_task_types": ["rag_retrieval", "citation_validity"],
        "required_fields": [
            "source_id",
            "source_class",
            "jurisdiction",
            "text_span",
            "label",
            "annotator_or_generation_method",
            "confidence",
            "hash",
            "created_at",
            "review_status",
            "private_data_allowed_for_training",
        ],
        "required_gold_dataset_minimums": {
            "maine_rag_retrieval_gold.jsonl": 2,
            "maine_citation_validity_gold.jsonl": 2,
        },
        "attorney_review_required": True,
        "private_data_training_allowed": False,
    }


def test_pass26_annotation_queue_assigns_double_review_and_exports_csv(tmp_path):
    manifest = _manifest(tmp_path)
    queue = tmp_path / "eval_store" / "gold_annotation_queue.jsonl"
    csv_output = tmp_path / "eval_store" / "gold_annotation_queue.csv"

    result = GoldAnnotationQueueBuilder(policy=_policy()).build_from_manifest(
        manifest_path=manifest,
        output_path=queue,
        max_items_per_task_type=1,
        reviewer_ids=["attorney_a", "attorney_b"],
        double_review=True,
        csv_output_path=csv_output,
    )
    audit = GoldAnnotationQueueAuditor().audit(queue)
    rows = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines()]

    assert result["queue_rows"] == 2
    assert result["assigned_rows"] == 2
    assert csv_output.exists()
    assert audit.status == "pass"
    assert audit.double_review_rows == 2
    assert all(row["review_status"] == "needs_attorney_review" for row in rows)
    assert all(row["promoted_gold_dataset"].endswith("_gold.jsonl") for row in rows)
    assert all(row["private_data_allowed_for_training"] is False for row in rows)


def test_pass27_gold_pack_manifest_blocks_until_attorney_minimums_are_met(tmp_path):
    eval_root = tmp_path / "eval_data"
    eval_root.mkdir()
    row = {
        "source_id": "source-1",
        "source_class": "statute_title_index",
        "jurisdiction": "maine",
        "text_span": "Example span",
        "label": ["divorce"],
        "annotator_or_generation_method": "synthetic_seed_for_schema_validation",
        "confidence": 0.5,
        "hash": "abc",
        "created_at": "2026-05-16T00:00:00+00:00",
        "review_status": "seed_not_attorney_reviewed",
        "private_data_allowed_for_training": False,
    }
    (eval_root / "maine_rag_retrieval_gold.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    manifest = GoldEvalPackManifestBuilder(policy=_policy()).build(
        eval_root=eval_root,
        output_path=tmp_path / "gold_eval_pack_manifest.json",
    )

    assert manifest["production_ready"] is False
    assert any(blocker.startswith("gold_rows_minimum_not_met") for blocker in manifest["blockers"])
    assert (tmp_path / "gold_eval_pack_manifest.json").exists()


def test_pass28_release_metrics_evidence_reports_missing_metrics_and_blocks_ga(tmp_path):
    eval_root = tmp_path / "eval_data"
    eval_root.mkdir()
    report = ReleaseMetricsEvidenceBuilder(project_root=Path.cwd(), eval_root=eval_root).build(
        output_path=tmp_path / "release_metrics_evidence.json",
    )
    by_name = {metric.name: metric for metric in report.metrics}

    assert report.status == "pass"
    assert report.release_gate_report["release_allowed"] is False
    assert by_name["private_data_packaging"].value == 1.0
    assert by_name["retrieval_recall_at_20"].value is None
    assert by_name["citation_existence"].pass_fail == "block"
    assert report.blockers
    assert (tmp_path / "release_metrics_evidence.json").exists()
