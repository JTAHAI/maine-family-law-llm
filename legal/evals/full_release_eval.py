from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.release_metrics import ReleaseMetricsEvidenceBuilder
from legal.production.release_gates import DEFAULT_RELEASE_THRESHOLDS, ReleaseGateRunner, ReleaseMetric


@dataclass(frozen=True)
class FullReleaseEvalReport:
    """Pass 46 ship/no-ship release evaluation report.

    The report is intentionally strict: release is allowed only when every GA
    metric is measured from non-seed, non-synthetic evidence, minimum sample
    sizes are met, attorney-review requirements are met, and thresholds pass.
    """

    status: str
    generated_at: str
    eval_root: str
    ship_decision: str
    release_allowed: bool
    ga_thresholds: dict[str, dict[str, Any]]
    metrics: list[dict[str, Any]] = field(default_factory=list)
    gate_report: dict[str, Any] = field(default_factory=dict)
    evidence_basis: str = "release_metrics_evidence"
    blockers: list[str] = field(default_factory=list)
    readiness: str = "no_ship"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "eval_root": self.eval_root,
            "ship_decision": self.ship_decision,
            "release_allowed": self.release_allowed,
            "readiness": self.readiness,
            "ga_thresholds": self.ga_thresholds,
            "metrics": self.metrics,
            "gate_report": self.gate_report,
            "evidence_basis": self.evidence_basis,
            "blockers": sorted(set(self.blockers)),
        }


class FullReleaseEvalRunner:
    """Run Pass 46 full release eval from explicit release metric evidence."""

    def __init__(self, *, project_root: str | Path = ".", eval_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.project_root / "eval_data"
        self.gate_runner = ReleaseGateRunner()

    def run(
        self,
        *,
        measured_metrics: dict[str, ReleaseMetric | dict[str, Any] | float | None] | None = None,
        output_path: str | Path | None = None,
    ) -> FullReleaseEvalReport:
        """Return a ship/no-ship report.

        If `measured_metrics` is omitted, the runner builds release metrics from
        the configured eval root. That path will correctly block GA in this repo
        until real attorney-reviewed gold rows and source freshness evidence are
        supplied from external stores.
        """
        if measured_metrics is None:
            evidence = ReleaseMetricsEvidenceBuilder(
                project_root=self.project_root,
                eval_root=self.eval_root,
            ).build()
            metrics_for_gate = {metric.name: metric.as_metric() for metric in evidence.metrics}
            metrics = [metric.as_dict() for metric in evidence.metrics]
            evidence_blockers = list(evidence.blockers)
            evidence_basis = "release_metrics_evidence_builder"
        else:
            metrics_for_gate = measured_metrics
            metrics = [self.gate_runner._coerce_metric(name, value).as_dict() for name, value in measured_metrics.items()]
            evidence_blockers = []
            evidence_basis = "explicit_measured_metrics"

        gate_report = self.gate_runner.evaluate(metrics_for_gate).as_dict()
        blockers = sorted(set(evidence_blockers + list(gate_report.get("blockers", []))))
        release_allowed = bool(gate_report.get("release_allowed")) and not blockers
        report = FullReleaseEvalReport(
            status="pass",
            generated_at=datetime.now(timezone.utc).isoformat(),
            eval_root=str(self.eval_root),
            ship_decision="ship" if release_allowed else "no_ship",
            release_allowed=release_allowed,
            ga_thresholds=DEFAULT_RELEASE_THRESHOLDS,
            metrics=metrics,
            gate_report=gate_report,
            evidence_basis=evidence_basis,
            blockers=blockers,
            readiness=(
                "ga_release_eval_passed"
                if release_allowed
                else "ga_release_eval_no_ship_until_all_thresholds_real_gold_and_signoffs_pass"
            ),
        )
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def build_passing_fixture_metrics() -> dict[str, ReleaseMetric]:
    """Small helper for tests and docs; not used by production release runs."""
    return {
        "retrieval_recall_at_20": ReleaseMetric(
            "retrieval_recall_at_20", 0.96, "attorney_reviewed_release_eval", 500, True
        ),
        "citation_existence": ReleaseMetric(
            "citation_existence", 0.995, "attorney_reviewed_release_eval", 500, True
        ),
        "citation_support": ReleaseMetric(
            "citation_support", 0.96, "attorney_reviewed_release_eval", 500, True
        ),
        "quote_span_verification": ReleaseMetric(
            "quote_span_verification", 0.98, "attorney_reviewed_release_eval", 500, True
        ),
        "hallucination_rate": ReleaseMetric(
            "hallucination_rate", 0.02, "attorney_reviewed_release_eval", 250, True
        ),
        "filing_gate_false_pass_rate": ReleaseMetric(
            "filing_gate_false_pass_rate", 0.0, "attorney_reviewed_release_eval", 100, True
        ),
        "form_freshness_detection": ReleaseMetric(
            "form_freshness_detection", 0.99, "attorney_reviewed_release_eval", 100, True
        ),
        "private_data_packaging": ReleaseMetric(
            "private_data_packaging", 1.0, "automated_repo_packaging_audit", 1, False
        ),
        "source_freshness_report_present": ReleaseMetric(
            "source_freshness_report_present", 1.0, "external_source_update_report", 1, False
        ),
        "attorney_review_sample_present": ReleaseMetric(
            "attorney_review_sample_present", 1.0, "attorney_reviewed_gold_eval_rows", 50, True
        ),
    }
