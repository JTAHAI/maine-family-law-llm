from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.production.release_gates import ReleaseGateRunner

EXTERNAL_TASK_METRICS = {
    "retrieval_recall_at_20",
    "citation_existence",
    "citation_support",
    "quote_span_verification",
    "hallucination_rate",
    "filing_gate_false_pass_rate",
    "form_freshness_detection",
}

METRIC_TO_GOLD_DATASET = {
    "retrieval_recall_at_20": "maine_rag_retrieval_gold.jsonl",
    "citation_existence": "maine_citation_validity_gold.jsonl",
    "citation_support": "maine_citation_validity_gold.jsonl",
    "quote_span_verification": "maine_quote_span_gold.jsonl",
    "hallucination_rate": "maine_hallucination_negative_cases.jsonl",
    "filing_gate_false_pass_rate": "maine_drafting_review_gold.jsonl",
    "form_freshness_detection": "maine_forms_freshness_gold.jsonl",
}

DISALLOWED_BASIS_MARKERS = ("seed", "synthetic", "fixture", "smoke", "source-derived", "source_derived")


@dataclass(frozen=True)
class ReleaseMetricMeasurementFinding:
    metric: str | None
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ReleaseMetricMeasurementStatus:
    metric: str
    value: float | None
    sample_size: int
    basis: str
    attorney_reviewed: bool
    reviewer_status: str
    source_dataset: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ReleaseMetricMeasurementAuditReport:
    status: str
    generated_at: str
    measurement_path: str
    required_metrics: list[str] = field(default_factory=list)
    metric_statuses: list[ReleaseMetricMeasurementStatus] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    findings: list[ReleaseMetricMeasurementFinding] = field(default_factory=list)
    readiness: str = "release_metric_measurements_blocked"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "measurement_path": self.measurement_path,
            "required_metrics": self.required_metrics,
            "metric_statuses": [item.as_dict() for item in self.metric_statuses],
            "blockers": sorted(set(self.blockers)),
            "findings": [item.as_dict() for item in self.findings],
        }


class ReleaseMetricMeasurementTemplateBuilder:
    """Build the external measurement file expected by release metrics evidence.

    The template intentionally contains null values and zero samples; it cannot pass
    release gates until task-specific evaluators fill it with measured results over
    attorney-reviewed gold JSONL rows.
    """

    def __init__(self, *, gate_runner: ReleaseGateRunner | None = None) -> None:
        self.gate_runner = gate_runner or ReleaseGateRunner()

    def build(self) -> dict[str, Any]:
        thresholds = self.gate_runner.thresholds
        metrics: list[dict[str, Any]] = []
        for name in required_external_metric_names(self.gate_runner):
            rule = thresholds[name]
            metrics.append(
                {
                    "name": name,
                    "value": None,
                    "sample_size": 0,
                    "basis": "fill_with_external_task_specific_evaluator_over_attorney_reviewed_gold",
                    "attorney_reviewed": True,
                    "reviewer_status": "attorney_reviewed_required",
                    "source_dataset": METRIC_TO_GOLD_DATASET[name],
                    "minimum_sample_size": int(rule.get("minimum_sample_size", 0) or 0),
                    "operator": rule.get("operator"),
                    "target": rule.get("target"),
                    "notes": "Do not use seed, synthetic, fixture, or smoke metrics for GA.",
                }
            )
        return {
            "schema_version": "release_metric_measurements_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "readiness": "template_only_not_release_evidence",
            "metrics": metrics,
        }

    def write(self, output_path: str | Path) -> dict[str, Any]:
        payload = self.build()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload


class ReleaseMetricMeasurementAuditor:
    """Fail-closed audit for task-specific GA metric measurement files."""

    def __init__(self, *, project_root: str | Path = ".", gate_runner: ReleaseGateRunner | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.gate_runner = gate_runner or ReleaseGateRunner()

    def audit(
        self,
        *,
        measurement_path: str | Path,
        output_path: str | Path | None = None,
        allow_repo_path: bool = False,
    ) -> ReleaseMetricMeasurementAuditReport:
        path = Path(measurement_path).resolve()
        required = required_external_metric_names(self.gate_runner)
        blockers: list[str] = []
        findings: list[ReleaseMetricMeasurementFinding] = []
        statuses: list[ReleaseMetricMeasurementStatus] = []

        if not path.exists():
            blockers.append("metric_measurement_file_missing")
            findings.append(
                ReleaseMetricMeasurementFinding(
                    metric=None,
                    code="metric_measurement_file_missing",
                    message=str(path),
                )
            )
            return self._finish(path, output_path, required, statuses, blockers, findings)

        if not allow_repo_path and _is_relative_to(path, self.project_root):
            blockers.append("metric_measurements_must_be_external_for_ga")
            findings.append(
                ReleaseMetricMeasurementFinding(
                    metric=None,
                    code="metric_measurements_must_be_external_for_ga",
                    message="Store release metric measurements in the external eval/release evidence root, not the source repo.",
                )
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append("metric_measurement_file_parse_error")
            findings.append(
                ReleaseMetricMeasurementFinding(
                    metric=None,
                    code="metric_measurement_file_parse_error",
                    message=str(exc),
                )
            )
            return self._finish(path, output_path, required, statuses, blockers, findings)

        rows = _normalize_metric_payload(payload)
        if rows is None:
            blockers.append("metric_measurement_file_malformed")
            findings.append(
                ReleaseMetricMeasurementFinding(
                    metric=None,
                    code="metric_measurement_file_malformed",
                    message="Expected a JSON object with metrics list/dict or a list of metric objects.",
                )
            )
            return self._finish(path, output_path, required, statuses, blockers, findings)

        by_name = {str(row.get("name")): row for row in rows if isinstance(row, dict) and row.get("name")}
        for name in required:
            row = by_name.get(name)
            if row is None:
                blockers.append(f"metric_measurement_missing:{name}")
                findings.append(
                    ReleaseMetricMeasurementFinding(
                        metric=name,
                        code="metric_measurement_missing",
                        message="Required external task metric is absent.",
                    )
                )
                statuses.append(_blocked_status(name, "blocked_missing_metric"))
                continue
            statuses.append(self._audit_metric(name, row, blockers, findings))

        extra_names = sorted(set(by_name) - set(required))
        for name in extra_names:
            findings.append(
                ReleaseMetricMeasurementFinding(
                    metric=name,
                    code="metric_measurement_extra",
                    message="Extra metric ignored by GA task-specific measurement audit.",
                )
            )

        return self._finish(path, output_path, required, statuses, blockers, findings)

    def _audit_metric(
        self,
        name: str,
        row: dict[str, Any],
        blockers: list[str],
        findings: list[ReleaseMetricMeasurementFinding],
    ) -> ReleaseMetricMeasurementStatus:
        rule = self.gate_runner.thresholds[name]
        metric_blockers: list[str] = []
        value: float | None
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            value = None
            metric_blockers.append("metric_value_missing_or_non_numeric")

        try:
            sample_size = int(row.get("sample_size", 0) or 0)
        except (TypeError, ValueError):
            sample_size = 0
            metric_blockers.append("metric_sample_size_invalid")

        basis = str(row.get("basis", ""))
        reviewer_status = str(row.get("reviewer_status", ""))
        attorney_reviewed = bool(row.get("attorney_reviewed", False))
        source_dataset = str(row.get("source_dataset", ""))
        minimum_sample = int(rule.get("minimum_sample_size", 0) or 0)

        if sample_size < minimum_sample:
            metric_blockers.append("metric_sample_size_below_release_gate_minimum")
        if not attorney_reviewed:
            metric_blockers.append("metric_missing_attorney_review_flag")
        if "attorney" not in reviewer_status.lower():
            metric_blockers.append("metric_reviewer_status_not_attorney_reviewed")
        if not basis:
            metric_blockers.append("metric_basis_missing")
        if any(marker in basis.lower() for marker in DISALLOWED_BASIS_MARKERS):
            metric_blockers.append("metric_basis_disallowed_for_ga")
        expected_dataset = METRIC_TO_GOLD_DATASET[name]
        if source_dataset != expected_dataset:
            metric_blockers.append("metric_source_dataset_mismatch")

        for code in metric_blockers:
            blockers.append(f"{code}:{name}")
            findings.append(
                ReleaseMetricMeasurementFinding(metric=name, code=code, message=_finding_message(code, name))
            )

        return ReleaseMetricMeasurementStatus(
            metric=name,
            value=value,
            sample_size=sample_size,
            basis=basis,
            attorney_reviewed=attorney_reviewed,
            reviewer_status=reviewer_status,
            source_dataset=source_dataset,
            status="pass" if not metric_blockers else "blocked",
        )

    def _finish(
        self,
        path: Path,
        output_path: str | Path | None,
        required: list[str],
        statuses: list[ReleaseMetricMeasurementStatus],
        blockers: list[str],
        findings: list[ReleaseMetricMeasurementFinding],
    ) -> ReleaseMetricMeasurementAuditReport:
        report = ReleaseMetricMeasurementAuditReport(
            status="pass" if not blockers else "blocked",
            readiness="release_metric_measurements_ready" if not blockers else "release_metric_measurements_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            measurement_path=str(path),
            required_metrics=required,
            metric_statuses=statuses,
            blockers=blockers,
            findings=findings,
        )
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def required_external_metric_names(gate_runner: ReleaseGateRunner | None = None) -> list[str]:
    runner = gate_runner or ReleaseGateRunner()
    return [name for name in runner.required_metric_names() if name in EXTERNAL_TASK_METRICS]


def _normalize_metric_payload(payload: Any) -> list[dict[str, Any]] | None:
    metrics_payload = payload.get("metrics", payload) if isinstance(payload, dict) else payload
    if isinstance(metrics_payload, list):
        return [item for item in metrics_payload if isinstance(item, dict)]
    if isinstance(metrics_payload, dict):
        rows: list[dict[str, Any]] = []
        for name, item in metrics_payload.items():
            if isinstance(item, dict):
                rows.append({"name": str(name), **item})
            else:
                rows.append({"name": str(name), "value": item})
        return rows
    return None


def _blocked_status(name: str, status: str) -> ReleaseMetricMeasurementStatus:
    return ReleaseMetricMeasurementStatus(
        metric=name,
        value=None,
        sample_size=0,
        basis="missing",
        attorney_reviewed=False,
        reviewer_status="missing",
        source_dataset=METRIC_TO_GOLD_DATASET.get(name, ""),
        status=status,
    )


def _finding_message(code: str, name: str) -> str:
    if code == "metric_value_missing_or_non_numeric":
        return "Metric must provide a numeric measured value."
    if code == "metric_sample_size_below_release_gate_minimum":
        return "Metric sample size is below the release gate minimum."
    if code == "metric_missing_attorney_review_flag":
        return "Legal-quality metric must be marked attorney_reviewed=true."
    if code == "metric_reviewer_status_not_attorney_reviewed":
        return "reviewer_status must identify attorney-reviewed measurement evidence."
    if code == "metric_basis_missing":
        return "Metric basis must describe the external evaluator and dataset."
    if code == "metric_basis_disallowed_for_ga":
        return "Seed, synthetic, fixture, smoke, and source-derived metrics do not satisfy GA."
    if code == "metric_source_dataset_mismatch":
        return f"Metric must identify source_dataset={METRIC_TO_GOLD_DATASET.get(name, '<unknown>')}"
    return code


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
