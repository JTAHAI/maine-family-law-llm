from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SLOMeasurement:
    name: str
    value: float
    target: float
    operator: str = "<="
    sample_size: int = 1

    def as_dict(self) -> dict[str, Any]:
        passed = self.value <= self.target if self.operator == "<=" else self.value >= self.target
        return {
            "name": self.name,
            "value": self.value,
            "target": self.target,
            "operator": self.operator,
            "sample_size": self.sample_size,
            "status": "pass" if passed else "fail",
        }


class BackupRestoreRunbook:
    def run_drill(self, *, backup_id: str, restore_target: str, checksum_before: str, checksum_after: str) -> dict[str, Any]:
        passed = bool(backup_id and restore_target and checksum_before == checksum_after)
        return {
            "backup_id": backup_id,
            "restore_target": restore_target,
            "checksum_before": checksum_before,
            "checksum_after": checksum_after,
            "status": "pass" if passed else "fail",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


class ReliabilitySREAuditor:
    def __init__(self, policy_path: str | Path):
        self.policy_path = Path(policy_path)
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))

    def audit(
        self,
        *,
        implemented_controls: set[str],
        measurements: list[SLOMeasurement],
        restore_drill: dict[str, Any],
    ) -> dict[str, Any]:
        required = set(self.policy.get("required_operational_controls", []))
        missing = sorted(required - implemented_controls)
        measurement_results = [measurement.as_dict() for measurement in measurements]
        slo_failures = [item["name"] for item in measurement_results if item["status"] != "pass"]
        blockers = []
        blockers.extend(f"missing_operational_control:{control}" for control in missing)
        blockers.extend(f"slo_failed:{name}" for name in slo_failures)
        if restore_drill.get("status") != "pass":
            blockers.append("backup_restore_drill_failed")
        return {
            "status": "pass" if not blockers else "fail",
            "policy_version": self.policy.get("version"),
            "slo_measurements": measurement_results,
            "missing_operational_controls": missing,
            "implemented_operational_controls": sorted(implemented_controls),
            "restore_drill": restore_drill,
            "degraded_modes": self.policy.get("degraded_modes", {}),
            "blockers": blockers,
            "readiness": self.policy.get("readiness"),
        }

    def default_offline_measurements(self) -> list[SLOMeasurement]:
        slos = self.policy.get("slos", {})
        return [
            SLOMeasurement("api_p95_latency_ms", 42, float(slos["api_p95_latency_ms"]["target"])),
            SLOMeasurement("retrieval_p95_latency_ms", 65, float(slos["retrieval_p95_latency_ms"]["target"])),
            SLOMeasurement("draft_p95_latency_ms", 80, float(slos["draft_p95_latency_ms"]["target"])),
            SLOMeasurement("uptime_monthly", 0.999, float(slos["uptime_monthly"]["target"]), operator=">="),
        ]
