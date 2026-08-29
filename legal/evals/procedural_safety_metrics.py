"""Fail-closed procedural-safety evaluation over external reviewed scenarios."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.evals.citation_quote_metrics import read_jsonl, write_json
from legal.evals.review_modes import is_attorney_reviewed, is_seed_or_synthetic

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FRESHNESS = {"current", "fresh"}
PROCEDURAL_SCENARIOS = {"deadline", "service", "posture", "forms", "venue", "filing"}


@dataclass
class ProceduralSafetyMetricReport:
    status: str
    readiness: str
    generated_at: str
    scenario_total: int = 0
    scenario_correct: int = 0
    procedural_safety_detection: float = 0.0
    scenario_type_counts: dict[str, int] = field(default_factory=dict)
    provenance_rows: int = 0
    blockers: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "scenario_total": self.scenario_total,
            "scenario_correct": self.scenario_correct,
            "procedural_safety_detection": self.procedural_safety_detection,
            "scenario_type_counts": self.scenario_type_counts,
            "provenance_rows": self.provenance_rows,
            "blockers": sorted(set(self.blockers)),
            "findings": self.findings,
        }


class ProceduralSafetyMetricRunner:
    """Run source-provenanced negative scenarios through the canonical filing gate.

    This is an evaluation harness, not a procedural decision engine.  Each
    reviewed row supplies only an opaque scenario payload and expected blocker
    codes; the runner asks the product gate whether those blockers remain in
    force.  A happy-path or a label-only fixture cannot satisfy strict mode.
    """

    def run(
        self,
        *,
        eval_root: str | Path,
        output_path: str | Path | None = None,
        strict_provenance: bool = False,
    ) -> ProceduralSafetyMetricReport:
        dataset = Path(eval_root) / "maine_procedural_safety_gold.jsonl"
        rows = list(read_jsonl(dataset)) if dataset.exists() else []
        blockers: list[str] = []
        findings: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        total = correct = provenance_rows = 0
        if not rows:
            blockers.append("procedural_safety_gold_dataset_missing_or_empty")
        gate = FilingReadyGate()
        for row_number, row in enumerate(rows, start=1):
            scenario_type = str(row.get("scenario_type") or "").strip().casefold()
            if strict_provenance:
                errors = _provenance_errors(row, scenario_type)
                if errors:
                    blockers.extend(errors)
                    findings.extend({"row_number": row_number, "code": code} for code in errors)
                    continue
                provenance_rows += 1
            if scenario_type not in PROCEDURAL_SCENARIOS:
                blockers.append("procedural_scenario_type_invalid")
                findings.append({"row_number": row_number, "code": "procedural_scenario_type_invalid"})
                continue
            review_status = str(row.get("review_status") or row.get("reviewer_status") or "")
            method = str(row.get("annotator_or_generation_method") or row.get("basis") or "")
            if strict_provenance and (not is_attorney_reviewed(review_status, method) or is_seed_or_synthetic(review_status, method)):
                blockers.append("procedural_scenario_not_qualified_attorney_review")
                findings.append({"row_number": row_number, "code": "procedural_scenario_not_qualified_attorney_review"})
                continue
            expected = [str(value) for value in row.get("expected_blockers") or [] if str(value)]
            payload = row.get("filing_payload")
            if not isinstance(payload, dict) or not expected:
                blockers.append("procedural_scenario_payload_or_expected_blockers_missing")
                findings.append({"row_number": row_number, "code": "procedural_scenario_payload_or_expected_blockers_missing"})
                continue
            counts[scenario_type] = counts.get(scenario_type, 0) + 1
            total += 1
            actual = set(gate.evaluate(payload).get("blockers") or [])
            if all(_matches_expected(expected_code, actual) for expected_code in expected):
                correct += 1
            else:
                findings.append({"row_number": row_number, "code": "procedural_blocker_missing", "scenario_type": scenario_type, "expected_blockers": expected, "actual_blockers": sorted(actual)[:50]})
        if strict_provenance:
            for scenario_type in sorted(PROCEDURAL_SCENARIOS):
                if not counts.get(scenario_type):
                    blockers.append(f"procedural_scenario_coverage_missing:{scenario_type}")
        rate = round(correct / total, 6) if total else 0.0
        if total and rate < 1.0:
            blockers.append("procedural_safety_detection_below_100_percent")
        report = ProceduralSafetyMetricReport(
            status="pass" if not blockers else "blocked",
            readiness="procedural_safety_metrics_ready" if not blockers else "procedural_safety_metrics_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            scenario_total=total,
            scenario_correct=correct,
            procedural_safety_detection=rate,
            scenario_type_counts=counts,
            provenance_rows=provenance_rows,
            blockers=blockers,
            findings=findings,
        )
        if output_path:
            write_json(Path(output_path), report.as_dict())
        return report


def _provenance_errors(row: dict[str, Any], scenario_type: str) -> list[str]:
    errors: list[str] = []
    if scenario_type not in PROCEDURAL_SCENARIOS:
        errors.append("procedural_scenario_type_invalid")
    if not str(row.get("authority_build_id") or "").strip():
        errors.append("procedural_authority_build_id_missing")
    for field in ("source_snapshot_sha256", "reviewer_evidence_sha256"):
        if not _SHA256.fullmatch(str(row.get(field) or "").strip().casefold()):
            errors.append(f"procedural_{field}_invalid")
    if str(row.get("license_status") or "").strip().casefold() not in {"licensed_or_authorized", "license_verified_external"}:
        errors.append("procedural_license_status_unverified")
    if str(row.get("source_freshness") or "").strip().casefold() not in _FRESHNESS:
        errors.append("procedural_source_freshness_not_current")
    return errors


def _matches_expected(expected: str, actual: set[str]) -> bool:
    return any(value == expected or value.startswith(expected + ":") for value in actual)


__all__ = ["PROCEDURAL_SCENARIOS", "ProceduralSafetyMetricReport", "ProceduralSafetyMetricRunner"]
