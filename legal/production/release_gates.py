from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Production release gates are intentionally conservative. A metric must be
# measured from non-synthetic release evidence, meet its threshold, meet the
# minimum sample size, and satisfy attorney-review requirements for legal quality
# metrics. These values are mirrored in configs/maine_release_gates_policy.json.
DEFAULT_RELEASE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "retrieval_recall_at_20": {
        "operator": ">=", "target": 0.95, "required": True,
        "minimum_sample_size": 500, "requires_attorney_review": True,
    },
    "citation_existence": {
        "operator": ">=", "target": 0.99, "required": True,
        "minimum_sample_size": 500, "requires_attorney_review": True,
    },
    "citation_support": {
        "operator": ">=", "target": 0.95, "required": True,
        "minimum_sample_size": 500, "requires_attorney_review": True,
    },
    "quote_span_verification": {
        "operator": ">=", "target": 0.97, "required": True,
        "minimum_sample_size": 500, "requires_attorney_review": True,
    },
    "hallucination_rate": {
        "operator": "<=", "target": 0.03, "required": True,
        "minimum_sample_size": 250, "requires_attorney_review": True,
    },
    "filing_gate_false_pass_rate": {
        "operator": "==", "target": 0.0, "required": True,
        "minimum_sample_size": 100, "requires_attorney_review": True,
    },
    "form_freshness_detection": {
        "operator": ">=", "target": 0.99, "required": True,
        "minimum_sample_size": 100, "requires_attorney_review": True,
    },
    "private_data_packaging": {
        "operator": "==", "target": 1.0, "required": True,
        "minimum_sample_size": 1, "requires_attorney_review": False,
    },
    "source_freshness_report_present": {
        "operator": "==", "target": 1.0, "required": True,
        "minimum_sample_size": 1, "requires_attorney_review": False,
    },
    "attorney_review_sample_present": {
        "operator": "==", "target": 1.0, "required": True,
        "minimum_sample_size": 50, "requires_attorney_review": True,
    },
}


@dataclass(frozen=True)
class ReleaseMetric:
    name: str
    value: float | None
    basis: str
    sample_size: int = 0
    attorney_reviewed: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "basis": self.basis,
            "sample_size": self.sample_size,
            "attorney_reviewed": self.attorney_reviewed,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReleaseGateResult:
    metric: str
    status: str
    value: float | None
    target: float
    operator: str
    blocker: str | None = None
    basis: str = ""
    sample_size: int = 0
    attorney_reviewed: bool = False
    minimum_sample_size: int = 0
    requires_attorney_review: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "status": self.status,
            "value": self.value,
            "target": self.target,
            "operator": self.operator,
            "blocker": self.blocker,
            "basis": self.basis,
            "sample_size": self.sample_size,
            "minimum_sample_size": self.minimum_sample_size,
            "attorney_reviewed": self.attorney_reviewed,
            "requires_attorney_review": self.requires_attorney_review,
        }


@dataclass
class ReleaseReadinessReport:
    gate_results: list[ReleaseGateResult] = field(default_factory=list)
    release_allowed: bool = False
    readiness: str = "production_release_blocked"
    blockers: list[str] = field(default_factory=list)
    required_metrics: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "release_allowed": self.release_allowed,
            "readiness": self.readiness,
            "blockers": self.blockers,
            "required_metrics": self.required_metrics,
            "gate_results": [result.as_dict() for result in self.gate_results],
        }


class ReleaseGateRunner:
    """Evaluate production release gates from explicit measured metrics.

    The runner is deliberately conservative. Missing metrics, seed/synthetic
    metrics, undersized samples, and missing attorney review for legal-quality
    gates block production release. This prevents the source repo from passing as
    an enterprise legal product merely because placeholder scaffolds exist.
    """

    def __init__(self, thresholds: dict[str, dict[str, Any]] | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_RELEASE_THRESHOLDS

    def evaluate(self, metrics: dict[str, ReleaseMetric | dict[str, Any] | float | None]) -> ReleaseReadinessReport:
        results: list[ReleaseGateResult] = []
        blockers: list[str] = []

        for metric_name, rule in self.thresholds.items():
            metric = self._coerce_metric(metric_name, metrics.get(metric_name))
            result = self._evaluate_metric(metric, rule)
            results.append(result)
            if result.blocker:
                blockers.append(result.blocker)

        return ReleaseReadinessReport(
            gate_results=results,
            release_allowed=not blockers,
            readiness="production_release_allowed" if not blockers else "production_release_blocked",
            blockers=sorted(set(blockers)),
            required_metrics=sorted(self.thresholds),
        )

    def required_metric_names(self) -> list[str]:
        return sorted(self.thresholds)

    def _coerce_metric(self, name: str, value: ReleaseMetric | dict[str, Any] | float | None) -> ReleaseMetric:
        if isinstance(value, ReleaseMetric):
            return value
        if isinstance(value, dict):
            return ReleaseMetric(
                name=name,
                value=value.get("value"),
                basis=value.get("basis", "unknown"),
                sample_size=int(value.get("sample_size", 0) or 0),
                attorney_reviewed=bool(value.get("attorney_reviewed", False)),
                notes=value.get("notes", ""),
            )
        if value is None:
            return ReleaseMetric(name=name, value=None, basis="missing")
        return ReleaseMetric(name=name, value=float(value), basis="numeric_input")

    def _result(
        self,
        metric: ReleaseMetric,
        rule: dict[str, Any],
        *,
        status: str,
        blocker: str | None,
    ) -> ReleaseGateResult:
        return ReleaseGateResult(
            metric=metric.name,
            status=status,
            value=metric.value,
            target=float(rule["target"]),
            operator=str(rule["operator"]),
            blocker=blocker,
            basis=metric.basis,
            sample_size=metric.sample_size,
            attorney_reviewed=metric.attorney_reviewed,
            minimum_sample_size=int(rule.get("minimum_sample_size", 0) or 0),
            requires_attorney_review=bool(rule.get("requires_attorney_review", False)),
        )

    def _evaluate_metric(self, metric: ReleaseMetric, rule: dict[str, Any]) -> ReleaseGateResult:
        operator = str(rule["operator"])
        target = float(rule["target"])
        minimum_sample_size = int(rule.get("minimum_sample_size", 0) or 0)
        requires_attorney_review = bool(rule.get("requires_attorney_review", False))

        if metric.value is None:
            return self._result(
                metric,
                rule,
                status="blocked_missing_metric",
                blocker=f"missing_metric:{metric.name}",
            )

        basis = metric.basis.lower()
        if "seed" in basis or "synthetic" in basis:
            return self._result(
                metric,
                rule,
                status="blocked_insufficient_basis",
                blocker=f"insufficient_metric_basis:{metric.name}",
            )

        if metric.sample_size < minimum_sample_size:
            return self._result(
                metric,
                rule,
                status="blocked_minimum_sample_size",
                blocker=f"minimum_sample_size_not_met:{metric.name}",
            )

        if requires_attorney_review and not metric.attorney_reviewed:
            return self._result(
                metric,
                rule,
                status="blocked_attorney_review_missing",
                blocker=f"attorney_review_missing:{metric.name}",
            )

        passed = _compare(metric.value, operator, target)
        return self._result(
            metric,
            rule,
            status="pass" if passed else "fail",
            blocker=None if passed else f"threshold_failed:{metric.name}",
        )


def _compare(value: float, operator: str, target: float) -> bool:
    if operator == ">=":
        return value >= target
    if operator == "<=":
        return value <= target
    if operator == "==":
        return value == target
    raise ValueError(f"unsupported release gate operator: {operator}")
