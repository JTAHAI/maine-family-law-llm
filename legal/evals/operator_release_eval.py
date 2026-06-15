from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPERATOR_RELEASE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "retrieval_recall_at_20": {"operator": ">=", "target": 0.90, "minimum_sample_size": 1},
    "citation_existence": {"operator": ">=", "target": 0.99, "minimum_sample_size": 1},
    "quote_span_verification": {"operator": ">=", "target": 0.97, "minimum_sample_size": 1},
    "citation_support": {"operator": ">=", "target": 0.95, "minimum_sample_size": 1},
    "scope_verification": {"operator": ">=", "target": 1.0, "minimum_sample_size": 1},
    "form_freshness_detection": {"operator": ">=", "target": 0.99, "minimum_sample_size": 1},
    "source_freshness_report_present": {"operator": "==", "target": 1.0, "minimum_sample_size": 1},
    "private_data_packaging": {"operator": "==", "target": 1.0, "minimum_sample_size": 1},
}


@dataclass(frozen=True)
class OperatorReleaseMetric:
    name: str
    value: float | None
    sample_size: int
    basis: str
    source_path: str = ""
    operator_source_backed: bool = False
    attorney_reviewed: bool = False
    reviewer_status: str = "unknown"
    status: str = "measured"
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "sample_size": self.sample_size,
            "basis": self.basis,
            "source_path": self.source_path,
            "operator_source_backed": self.operator_source_backed,
            "attorney_reviewed": self.attorney_reviewed,
            "reviewer_status": self.reviewer_status,
            "status": self.status,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class OperatorReleaseEvalReport:
    status: str
    readiness: str
    generated_at: str
    data_root: str
    eval_root: str
    operator_release_allowed: bool
    true_ga_release_allowed: bool
    attorney_reviewed: bool
    legal_signoff: bool
    pilot_signoff: bool
    metrics: list[OperatorReleaseMetric]
    thresholds: dict[str, dict[str, Any]] = field(default_factory=lambda: OPERATOR_RELEASE_THRESHOLDS)
    blockers: list[str] = field(default_factory=list)
    measurement_output_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "eval_root": self.eval_root,
            "operator_release_allowed": self.operator_release_allowed,
            "true_ga_release_allowed": self.true_ga_release_allowed,
            "attorney_reviewed": self.attorney_reviewed,
            "legal_signoff": self.legal_signoff,
            "pilot_signoff": self.pilot_signoff,
            "thresholds": self.thresholds,
            "metrics": [metric.as_dict() for metric in self.metrics],
            "blockers": sorted(set(self.blockers)),
            "measurement_output_path": self.measurement_output_path,
        }


class OperatorSourceBackedReleaseEvalRunner:
    """Pass 46 non-attorney release-eval lane.

    This runner is intentionally explicit about the boundary: it can pass an
    operator/source-backed engineering release-eval gate, but it never turns that
    into attorney review, pilot approval, legal signoff, or true GA shipment.
    """

    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def run(
        self,
        *,
        data_root: str | Path,
        eval_root: str | Path,
        output_path: str | Path | None = None,
        measurement_output_path: str | Path | None = None,
    ) -> OperatorReleaseEvalReport:
        data_root = Path(data_root).resolve()
        eval_root = Path(eval_root).resolve()
        metrics = self._collect_metrics(data_root=data_root, eval_root=eval_root)
        blockers = self._evaluate(metrics)
        operator_allowed = not blockers
        report = OperatorReleaseEvalReport(
            status="pass" if operator_allowed else "blocked",
            readiness=(
                "pass46_operator_source_backed_release_eval_ready"
                if operator_allowed
                else "pass46_operator_source_backed_release_eval_blocked"
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_root=str(data_root),
            eval_root=str(eval_root),
            operator_release_allowed=operator_allowed,
            true_ga_release_allowed=False,
            attorney_reviewed=False,
            legal_signoff=False,
            pilot_signoff=False,
            metrics=metrics,
            blockers=blockers,
            measurement_output_path=str(measurement_output_path) if measurement_output_path else None,
        )
        if measurement_output_path:
            self._write_measurements(report, Path(measurement_output_path))
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _collect_metrics(self, *, data_root: Path, eval_root: Path) -> list[OperatorReleaseMetric]:
        by_name: dict[str, OperatorReleaseMetric] = {}
        for path in self._measurement_candidates(data_root=data_root, eval_root=eval_root):
            for metric in _load_measurements(path):
                name = metric.name
                if name in OPERATOR_RELEASE_THRESHOLDS and name not in by_name:
                    by_name[name] = metric

        retrieval = self._retrieval_metric(data_root=data_root, eval_root=eval_root)
        if retrieval:
            by_name[retrieval.name] = retrieval
        source = self._source_freshness_metric(data_root=data_root, eval_root=eval_root)
        by_name[source.name] = source
        by_name["private_data_packaging"] = self._private_packaging_metric()

        return [
            by_name.get(name)
            or OperatorReleaseMetric(
                name=name,
                value=None,
                sample_size=0,
                basis="missing_operator_source_backed_metric",
                operator_source_backed=False,
                status="missing",
            )
            for name in OPERATOR_RELEASE_THRESHOLDS
        ]

    @staticmethod
    def _measurement_candidates(*, data_root: Path, eval_root: Path) -> list[Path]:
        names = [
            "release_metric_measurements.pass29.partial.json",
            "release_metric_measurements.pass30.partial.json",
            "release_metric_measurements.pass31.partial.json",
            "release_metric_measurements.operator_source_backed.json",
            "release_metric_measurements.json",
        ]
        roots = [data_root, eval_root, data_root / "release_evidence", eval_root / "release_evidence"]
        return [root / name for root in roots for name in names]

    @staticmethod
    def _retrieval_metric(*, data_root: Path, eval_root: Path) -> OperatorReleaseMetric | None:
        candidates = [
            data_root / "retrieval_smoke_report.json",
            eval_root / "retrieval_smoke_eval.json",
            eval_root / "retrieval_smoke_report.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            payload = _read_json(path)
            if not isinstance(payload, dict):
                continue
            metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
            value = metrics.get("recall_at_20")
            if value is None and isinstance(metrics.get("aggregate"), dict):
                value = metrics["aggregate"].get("recall_at_20")
            if value is None:
                value = payload.get("recall_at_20")
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            return OperatorReleaseMetric(
                name="retrieval_recall_at_20",
                value=numeric,
                sample_size=int(payload.get("case_count", 0) or metrics.get("case_count", 0) or 0),
                basis="source_backed_retrieval_smoke",
                source_path=str(path),
                operator_source_backed=True,
                reviewer_status="operator_source_backed",
            )
        return None

    @staticmethod
    def _source_freshness_metric(*, data_root: Path, eval_root: Path) -> OperatorReleaseMetric:
        candidates = [
            data_root / "source_update_report.json",
            data_root / "official_authority_store" / "source_update_report.json",
            eval_root / "source_update_report.json",
            data_root / "release_evidence" / "source_update_report.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            payload = _read_json(path)
            if isinstance(payload, dict) and (payload.get("status") == "pass" or payload.get("freshness_audit_passed") is True):
                return OperatorReleaseMetric(
                    name="source_freshness_report_present",
                    value=1.0,
                    sample_size=1,
                    basis="external_source_update_report",
                    source_path=str(path),
                    operator_source_backed=True,
                    reviewer_status="not_required",
                )
        return OperatorReleaseMetric(
            name="source_freshness_report_present",
            value=None,
            sample_size=0,
            basis="missing_external_source_update_report",
            operator_source_backed=False,
            status="missing",
            notes="Expected source_update_report.json from external authority build.",
        )

    def _private_packaging_metric(self) -> OperatorReleaseMetric:
        forbidden = [
            "ME_FM_LLM_data",
            "official_authority_store",
            "eval_store",
            "parsed_authority_store",
            "embedding_store",
        ]
        present = [name for name in forbidden if (self.project_root / name).exists()]
        return OperatorReleaseMetric(
            name="private_data_packaging",
            value=0.0 if present else 1.0,
            sample_size=1,
            basis="repo_packaging_boundary_audit",
            source_path=str(self.project_root),
            operator_source_backed=True,
            reviewer_status="not_required",
            status="measured" if not present else "blocked",
            notes="Forbidden runtime/external data directories present: " + ", ".join(present) if present else "No forbidden runtime/external data directories present in repo root.",
        )

    def _evaluate(self, metrics: list[OperatorReleaseMetric]) -> list[str]:
        blockers: list[str] = []
        by_name = {metric.name: metric for metric in metrics}
        for name, rule in OPERATOR_RELEASE_THRESHOLDS.items():
            metric = by_name.get(name)
            if metric is None or metric.value is None:
                blockers.append(f"missing_metric:{name}")
                continue
            if metric.sample_size < int(rule.get("minimum_sample_size", 0) or 0):
                blockers.append(f"minimum_sample_size_not_met:{name}")
            if not metric.operator_source_backed:
                blockers.append(f"operator_source_backed_missing:{name}")
            if not _compare(float(metric.value), str(rule["operator"]), float(rule["target"])):
                blockers.append(f"threshold_failed:{name}")
            basis = metric.basis.lower()
            if "seed" in basis or "synthetic" in basis or "fixture" in basis:
                blockers.append(f"insufficient_metric_basis:{name}")
        return sorted(set(blockers))

    @staticmethod
    def _write_measurements(report: OperatorReleaseEvalReport, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "operator_source_backed_release_metric_measurements_v1",
            "status": report.status,
            "review_mode": "operator_source_backed",
            "attorney_reviewed": False,
            "legal_signoff": False,
            "pilot_signoff": False,
            "generated_at": report.generated_at,
            "metrics": [metric.as_dict() for metric in report.metrics],
            "blockers": sorted(set(report.blockers)),
        }
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_measurements(path: Path) -> list[OperatorReleaseMetric]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    payload = _read_json(path)
    if payload is None:
        return []
    if isinstance(payload, dict):
        raw_metrics = payload.get("release_metric_measurements") or payload.get("metrics") or payload
    else:
        raw_metrics = payload
    rows: list[Any]
    if isinstance(raw_metrics, dict):
        rows = [{"name": name, **value} if isinstance(value, dict) else {"name": name, "value": value} for name, value in raw_metrics.items()]
    elif isinstance(raw_metrics, list):
        rows = raw_metrics
    else:
        rows = []
    loaded: list[OperatorReleaseMetric] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            value = None
        sample_size = int(row.get("sample_size", row.get("minimum_sample_size", 0)) or 0)
        loaded.append(
            OperatorReleaseMetric(
                name=str(row.get("name")),
                value=value,
                sample_size=sample_size,
                basis=str(row.get("basis") or row.get("evidence_basis") or path.name),
                source_path=str(path),
                operator_source_backed=bool(row.get("operator_source_backed")) or "operator_source_backed" in str(row.get("reviewer_status", "")).lower(),
                attorney_reviewed=bool(row.get("attorney_reviewed")),
                reviewer_status=str(row.get("reviewer_status") or "unknown"),
                status=str(row.get("status") or "measured"),
                notes=str(row.get("notes") or ""),
            )
        )
    return loaded


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _compare(value: float, operator: str, target: float) -> bool:
    if operator == ">=":
        return value >= target
    if operator == "<=":
        return value <= target
    if operator == "==":
        return value == target
    raise ValueError(f"unsupported operator={operator}")
