from __future__ import annotations

import json
from pathlib import Path

from legal.evals import (
    ReleaseMetricMeasurementAuditor,
    ReleaseMetricMeasurementTemplateBuilder,
    required_external_metric_names,
)


def test_release_metric_measurement_template_contains_required_external_metrics(tmp_path: Path) -> None:
    output = tmp_path / "release_metric_measurements.json"
    payload = ReleaseMetricMeasurementTemplateBuilder().write(output)
    names = {item["name"] for item in payload["metrics"]}

    assert names == set(required_external_metric_names())
    assert all(item["value"] is None for item in payload["metrics"])
    assert all(item["sample_size"] == 0 for item in payload["metrics"])
    assert output.exists()


def test_release_metric_measurement_auditor_blocks_template_values(tmp_path: Path) -> None:
    path = tmp_path / "release_metric_measurements.json"
    ReleaseMetricMeasurementTemplateBuilder().write(path)

    report = ReleaseMetricMeasurementAuditor(project_root=tmp_path / "repo").audit(
        measurement_path=path,
    )
    data = report.as_dict()

    assert data["status"] == "blocked"
    assert any("metric_value_missing_or_non_numeric" in item for item in data["blockers"])
    assert any("metric_sample_size_below_release_gate_minimum" in item for item in data["blockers"])


def test_release_metric_measurement_auditor_passes_complete_external_measurements(tmp_path: Path) -> None:
    path = tmp_path / "external" / "release_metric_measurements.json"
    path.parent.mkdir()
    metrics = []
    template = ReleaseMetricMeasurementTemplateBuilder().build()
    for row in template["metrics"]:
        minimum = int(row["minimum_sample_size"])
        value = 0.0 if row["name"] == "filing_gate_false_pass_rate" else 0.99
        if row["name"] == "hallucination_rate":
            value = 0.01
        metrics.append(
            {
                **row,
                "value": value,
                "sample_size": minimum,
                "basis": f"external_task_specific_evaluator_over_{row['source_dataset']}",
                "attorney_reviewed": True,
                "reviewer_status": "attorney_reviewed",
            }
        )
    path.write_text(json.dumps({"metrics": metrics}), encoding="utf-8")

    report = ReleaseMetricMeasurementAuditor(project_root=tmp_path / "repo").audit(
        measurement_path=path,
    )
    data = report.as_dict()

    assert data["status"] == "pass"
    assert data["blockers"] == []
    assert all(item["status"] == "pass" for item in data["metric_statuses"])


def test_release_metric_measurement_auditor_blocks_repo_local_metric_files(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    path = project / "release_metric_measurements.json"
    ReleaseMetricMeasurementTemplateBuilder().write(path)

    report = ReleaseMetricMeasurementAuditor(project_root=project).audit(measurement_path=path)

    assert "metric_measurements_must_be_external_for_ga" in report.as_dict()["blockers"]
