from __future__ import annotations

import json
from pathlib import Path

from legal.evals import ReleaseMetricsEvidenceBuilder

REQUIRED_FIELDS = [
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
]

DATASET_MINIMUMS = {
    "maine_rag_retrieval_gold.jsonl": 2,
    "maine_citation_validity_gold.jsonl": 2,
    "maine_quote_span_gold.jsonl": 2,
    "maine_hallucination_negative_cases.jsonl": 2,
    "maine_drafting_review_gold.jsonl": 2,
    "maine_forms_freshness_gold.jsonl": 2,
}


def _project_with_gold(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path / "project"
    eval_root = tmp_path / "external_eval"
    (project_root / "configs").mkdir(parents=True)
    eval_root.mkdir()
    (project_root / "configs" / "maine_gold_eval_pack_policy.json").write_text(
        json.dumps(
            {
                "version": "test-small-policy",
                "attorney_review_required": True,
                "private_data_training_allowed": False,
                "required_fields": REQUIRED_FIELDS,
                "required_gold_dataset_minimums": DATASET_MINIMUMS,
            }
        ),
        encoding="utf-8",
    )
    for dataset, rows in DATASET_MINIMUMS.items():
        with (eval_root / dataset).open("w", encoding="utf-8") as handle:
            for index in range(rows):
                handle.write(
                    json.dumps(
                        {
                            "source_id": f"source-{index}",
                            "source_class": "verified_official_maine",
                            "jurisdiction": "maine",
                            "text_span": "Reviewed source span",
                            "label": ["reviewed"],
                            "annotator_or_generation_method": "attorney_review",
                            "confidence": 0.99,
                            "hash": f"hash-{index}",
                            "created_at": "2026-05-30T00:00:00+00:00",
                            "review_status": "attorney_reviewed_final",
                            "private_data_allowed_for_training": False,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
    return project_root, eval_root


def test_release_metrics_require_task_specific_measurement_file(tmp_path: Path):
    project_root, eval_root = _project_with_gold(tmp_path)

    report = ReleaseMetricsEvidenceBuilder(project_root=project_root, eval_root=eval_root).build()
    by_name = {metric.name: metric for metric in report.metrics}

    assert by_name["retrieval_recall_at_20"].value is None
    assert by_name["retrieval_recall_at_20"].basis.startswith("missing_task_specific_metric")
    assert "missing_task_specific_release_metric_measurements" in report.blockers
    assert report.release_gate_report["release_allowed"] is False


def test_release_metrics_block_inflated_sample_counts(tmp_path: Path):
    project_root, eval_root = _project_with_gold(tmp_path)
    (eval_root / "release_metric_measurements.json").write_text(
        json.dumps(
            {
                "metrics": [
                    {
                        "name": "retrieval_recall_at_20",
                        "value": 0.99,
                        "sample_size": 500,
                        "basis": "attorney_reviewed_release_eval",
                        "attorney_reviewed": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = ReleaseMetricsEvidenceBuilder(project_root=project_root, eval_root=eval_root).build()
    by_name = {metric.name: metric for metric in report.metrics}

    assert by_name["retrieval_recall_at_20"].value is None
    assert by_name["retrieval_recall_at_20"].status == "blocked_measurement_integrity"
    assert "metric_sample_exceeds_attorney_reviewed_rows:retrieval_recall_at_20" in report.blockers


def test_release_metrics_accept_external_task_metric_but_still_apply_ga_thresholds(tmp_path: Path):
    project_root, eval_root = _project_with_gold(tmp_path)
    measurements = [
        {
            "name": name,
            "value": value,
            "sample_size": 2,
            "basis": "attorney_reviewed_release_eval",
            "attorney_reviewed": True,
        }
        for name, value in {
            "retrieval_recall_at_20": 0.99,
            "citation_existence": 1.0,
            "citation_support": 0.99,
            "quote_span_verification": 0.99,
            "hallucination_rate": 0.0,
            "filing_gate_false_pass_rate": 0.0,
            "form_freshness_detection": 1.0,
        }.items()
    ]
    (eval_root / "release_metric_measurements.json").write_text(
        json.dumps({"metrics": measurements}),
        encoding="utf-8",
    )
    (eval_root / "source_update_report.json").write_text(
        json.dumps({"status": "pass"}),
        encoding="utf-8",
    )

    report = ReleaseMetricsEvidenceBuilder(project_root=project_root, eval_root=eval_root).build()
    by_name = {metric.name: metric for metric in report.metrics}

    assert by_name["retrieval_recall_at_20"].value == 0.99
    assert by_name["source_freshness_report_present"].value == 1.0
    assert report.release_gate_report["release_allowed"] is False
    assert "minimum_sample_size_not_met:retrieval_recall_at_20" in report.blockers
