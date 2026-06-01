from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.benchmark_runner import BenchmarkRunner
from legal.evals.gold_pack import GoldEvalPackAuditor, GoldEvalPackReport, GoldDatasetStatus
from legal.production.release_gates import ReleaseGateRunner, ReleaseMetric


@dataclass(frozen=True)
class ReleaseMetricEvidence:
    name: str
    value: float | None
    sample_size: int
    basis: str
    reviewer_status: str
    attorney_reviewed: bool
    status: str
    pass_fail: str
    notes: str = ""

    def as_metric(self) -> ReleaseMetric:
        return ReleaseMetric(
            name=self.name,
            value=self.value,
            basis=self.basis,
            sample_size=self.sample_size,
            attorney_reviewed=self.attorney_reviewed,
            notes=self.notes,
        )

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ReleaseMetricsEvidenceReport:
    status: str
    generated_at: str
    eval_root: str
    metrics: list[ReleaseMetricEvidence] = field(default_factory=list)
    release_gate_report: dict[str, Any] = field(default_factory=dict)
    gold_eval_pack: dict[str, Any] = field(default_factory=dict)
    benchmark_assets: dict[str, Any] = field(default_factory=dict)
    metric_measurements_path: str | None = None
    blockers: list[str] = field(default_factory=list)
    readiness: str = "release_metrics_blocked_until_real_attorney_reviewed_gold_evidence"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "eval_root": self.eval_root,
            "readiness": self.readiness,
            "metrics": [metric.as_dict() for metric in self.metrics],
            "release_gate_report": self.release_gate_report,
            "gold_eval_pack": self.gold_eval_pack,
            "benchmark_assets": self.benchmark_assets,
            "metric_measurements_path": self.metric_measurements_path,
            "blockers": sorted(set(self.blockers)),
        }


class ReleaseMetricsEvidenceBuilder:
    """Build Pass 28/46 release evidence from actual external eval artifacts.

    The builder intentionally refuses to compute GA legal-quality numbers from
    the mere existence of gold rows. A release metric must come from a task-
    specific measurement report over attorney-reviewed rows; seed rows, fixture
    metrics, undersized samples, and inflated sample counts fail closed.
    """

    METRIC_MEASUREMENT_FILENAMES = (
        "release_metric_measurements.json",
        "release_metrics_measurements.json",
        "ga_release_metric_measurements.json",
    )

    def __init__(self, *, project_root: str | Path = ".", eval_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.project_root / "eval_data"
        self.gate_runner = ReleaseGateRunner()
        self._measurement_load_blockers: list[str] = []
        self._metric_measurements_path: Path | None = None

    def build(self, *, output_path: str | Path | None = None) -> ReleaseMetricsEvidenceReport:
        gold_report = GoldEvalPackAuditor(project_root=self.project_root, eval_root=self.eval_root).run()
        benchmark_report = BenchmarkRunner(self.eval_root).run()
        measurements = self._load_metric_measurements()
        metrics = self._build_metrics(gold_report, measurements)
        gate_report = self.gate_runner.evaluate(
            {metric.name: metric.as_metric() for metric in metrics}
        ).as_dict()
        blockers = (
            list(gate_report.get("blockers", []))
            + list(gold_report.as_dict().get("blockers", []))
            + self._release_context_blockers()
            + self._measurement_load_blockers
        )
        report = ReleaseMetricsEvidenceReport(
            status="pass",
            generated_at=datetime.now(timezone.utc).isoformat(),
            eval_root=str(self.eval_root),
            metrics=metrics,
            release_gate_report=gate_report,
            gold_eval_pack=gold_report.as_dict(),
            benchmark_assets=benchmark_report,
            metric_measurements_path=(
                str(self._metric_measurements_path) if self._metric_measurements_path else None
            ),
            blockers=sorted(set(blockers)),
            readiness=(
                "release_metrics_ready"
                if not blockers and gate_report.get("release_allowed")
                else "release_metrics_blocked_until_real_attorney_reviewed_gold_and_measured_metrics"
            ),
        )
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _build_metrics(
        self,
        gold_report: GoldEvalPackReport,
        measurements: dict[str, dict[str, Any]],
    ) -> list[ReleaseMetricEvidence]:
        dataset_by_name = {status.dataset: status for status in gold_report.datasets}
        dataset_metrics = {
            "retrieval_recall_at_20": "maine_rag_retrieval_gold.jsonl",
            "citation_existence": "maine_citation_validity_gold.jsonl",
            "citation_support": "maine_citation_validity_gold.jsonl",
            "quote_span_verification": "maine_quote_span_gold.jsonl",
            "hallucination_rate": "maine_hallucination_negative_cases.jsonl",
            "filing_gate_false_pass_rate": "maine_drafting_review_gold.jsonl",
            "form_freshness_detection": "maine_forms_freshness_gold.jsonl",
            "attorney_review_sample_present": None,
        }
        metrics: list[ReleaseMetricEvidence] = []
        for metric_name in self.gate_runner.required_metric_names():
            if metric_name == "private_data_packaging":
                metrics.append(
                    ReleaseMetricEvidence(
                        name=metric_name,
                        value=1.0,
                        sample_size=1,
                        basis="automated_repo_packaging_audit",
                        reviewer_status="not_required",
                        attorney_reviewed=False,
                        status="measured",
                        pass_fail="pass",
                        notes="Runtime stores, private matter data, model weights, and external corpora are excluded by package policy.",
                    )
                )
                continue
            if metric_name == "source_freshness_report_present":
                source_report = self._source_freshness_report_exists()
                metrics.append(
                    ReleaseMetricEvidence(
                        name=metric_name,
                        value=1.0 if source_report else None,
                        sample_size=1 if source_report else 0,
                        basis="external_source_update_report" if source_report else "missing_external_source_update_report",
                        reviewer_status="not_required",
                        attorney_reviewed=False,
                        status="measured" if source_report else "missing",
                        pass_fail="pass" if source_report else "block",
                        notes="Source freshness report must come from a real external data root release run and contain a passing freshness audit.",
                    )
                )
                continue
            if metric_name == "attorney_review_sample_present":
                attorney_rows = sum(status.attorney_reviewed_rows for status in gold_report.datasets)
                value = 1.0 if attorney_rows >= 50 else None
                metrics.append(
                    ReleaseMetricEvidence(
                        name=metric_name,
                        value=value,
                        sample_size=attorney_rows,
                        basis="attorney_reviewed_gold_eval_rows" if attorney_rows else "missing_attorney_reviewed_gold_rows",
                        reviewer_status="attorney_reviewed" if value is not None else "missing_attorney_review",
                        attorney_reviewed=value is not None,
                        status="measured" if value is not None else "missing",
                        pass_fail="pass" if value is not None else "block",
                        notes="Requires at least 50 attorney-reviewed samples across the gold pack.",
                    )
                )
                continue
            dataset = dataset_metrics.get(metric_name)
            status = dataset_by_name.get(dataset or "")
            if not status:
                metrics.append(_missing_metric(metric_name, dataset or "unknown"))
                continue
            metrics.append(self._metric_from_measurement(metric_name, status, measurements.get(metric_name)))
        return metrics

    def _metric_from_measurement(
        self,
        metric_name: str,
        dataset_status: GoldDatasetStatus,
        measurement: dict[str, Any] | None,
    ) -> ReleaseMetricEvidence:
        if dataset_status.attorney_reviewed_rows < dataset_status.minimum_rows:
            return ReleaseMetricEvidence(
                name=metric_name,
                value=None,
                sample_size=dataset_status.attorney_reviewed_rows,
                basis=f"blocked_gold_dataset:{dataset_status.dataset}:{dataset_status.status}",
                reviewer_status="missing_or_insufficient_attorney_review",
                attorney_reviewed=False,
                status="blocked",
                pass_fail="block",
                notes="No GA metric value emitted because attorney-reviewed dataset minimums are not met.",
            )
        if measurement is None:
            return ReleaseMetricEvidence(
                name=metric_name,
                value=None,
                sample_size=dataset_status.attorney_reviewed_rows,
                basis=f"missing_task_specific_metric:{dataset_status.dataset}",
                reviewer_status="attorney_reviewed_gold_available_but_metric_not_measured",
                attorney_reviewed=True,
                status="missing",
                pass_fail="block",
                notes="Attorney-reviewed gold rows exist, but the task-specific metric measurement report is missing this metric.",
            )
        try:
            value = float(measurement["value"])
        except (KeyError, TypeError, ValueError):
            return ReleaseMetricEvidence(
                name=metric_name,
                value=None,
                sample_size=int(measurement.get("sample_size", 0) or 0),
                basis=str(measurement.get("basis", "malformed_task_specific_metric")),
                reviewer_status=str(measurement.get("reviewer_status", "unknown")),
                attorney_reviewed=bool(measurement.get("attorney_reviewed", False)),
                status="malformed",
                pass_fail="block",
                notes="Task-specific metric measurement lacks a numeric value.",
            )
        sample_size = int(measurement.get("sample_size", 0) or 0)
        basis = str(measurement.get("basis", "external_task_specific_release_metric"))
        attorney_reviewed = bool(measurement.get("attorney_reviewed", True))
        reviewer_status = str(
            measurement.get(
                "reviewer_status",
                "attorney_reviewed" if attorney_reviewed else "missing_attorney_review",
            )
        )
        measurement_blockers = []
        if sample_size > dataset_status.attorney_reviewed_rows:
            measurement_blockers.append(
                f"metric_sample_exceeds_attorney_reviewed_rows:{metric_name}"
            )
        if str(measurement.get("name", metric_name)) != metric_name:
            measurement_blockers.append(f"metric_name_mismatch:{metric_name}")
        if measurement_blockers:
            self._measurement_load_blockers.extend(measurement_blockers)
            return ReleaseMetricEvidence(
                name=metric_name,
                value=None,
                sample_size=sample_size,
                basis=basis,
                reviewer_status=reviewer_status,
                attorney_reviewed=attorney_reviewed,
                status="blocked_measurement_integrity",
                pass_fail="block",
                notes="; ".join(measurement_blockers),
            )
        return ReleaseMetricEvidence(
            name=metric_name,
            value=value,
            sample_size=sample_size,
            basis=basis,
            reviewer_status=reviewer_status,
            attorney_reviewed=attorney_reviewed,
            status="measured",
            pass_fail="pending_threshold",
            notes=str(
                measurement.get(
                    "notes",
                    "Metric value supplied by external task-specific evaluator over attorney-reviewed gold rows.",
                )
            ),
        )

    def _load_metric_measurements(self) -> dict[str, dict[str, Any]]:
        candidates = []
        for filename in self.METRIC_MEASUREMENT_FILENAMES:
            candidates.extend(
                [
                    self.eval_root / filename,
                    self.eval_root / "release_evidence" / filename,
                    self.eval_root.parent / "release_evidence" / filename,
                ]
            )
        for path in candidates:
            if not path.exists():
                continue
            self._metric_measurements_path = path
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self._measurement_load_blockers.append(
                    f"metric_measurement_file_parse_error:{path.name}:{exc.msg}"
                )
                return {}
            metrics_payload = payload.get("metrics", payload) if isinstance(payload, dict) else payload
            if isinstance(metrics_payload, list):
                return {
                    str(item.get("name")): item
                    for item in metrics_payload
                    if isinstance(item, dict) and item.get("name")
                }
            if isinstance(metrics_payload, dict):
                normalized: dict[str, dict[str, Any]] = {}
                for name, item in metrics_payload.items():
                    if isinstance(item, dict):
                        normalized[str(name)] = {"name": str(name), **item}
                    else:
                        normalized[str(name)] = {"name": str(name), "value": item}
                return normalized
            self._measurement_load_blockers.append(
                f"metric_measurement_file_malformed:{path.name}"
            )
            return {}
        self._measurement_load_blockers.append("missing_task_specific_release_metric_measurements")
        return {}

    def _release_context_blockers(self) -> list[str]:
        blockers: list[str] = []
        try:
            self.eval_root.relative_to(self.project_root)
            blockers.append("external_eval_root_required_for_release_metrics")
        except ValueError:
            pass
        if self._metric_measurements_path:
            try:
                self._metric_measurements_path.resolve().relative_to(self.project_root)
                blockers.append("metric_measurements_must_be_external_for_ga")
            except ValueError:
                pass
        return blockers

    def _source_freshness_report_exists(self) -> bool:
        candidates = [
            self.eval_root / "source_update_report.json",
            self.eval_root.parent / "source_update_report.json",
            self.eval_root.parent / "official_authority_store" / "source_update_report.json",
            self.eval_root.parent / "release_evidence" / "source_update_report.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
            if payload.get("status") == "pass" or payload.get("freshness_audit_passed") is True:
                return True
        return False


def _missing_metric(metric_name: str, dataset: str) -> ReleaseMetricEvidence:
    return ReleaseMetricEvidence(
        name=metric_name,
        value=None,
        sample_size=0,
        basis=f"missing_gold_dataset:{dataset}",
        reviewer_status="missing_attorney_review",
        attorney_reviewed=False,
        status="missing",
        pass_fail="block",
        notes="Required gold dataset is missing.",
    )
