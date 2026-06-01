from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ControlCoverage:
    control: str
    implemented: bool
    evidence: str


class SecurityGovernanceChecklist:
    def __init__(self, policy_path: str | Path):
        self.policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))

    def required_controls(self) -> list[str]:
        return list(self.policy.get("required_controls", []))

    def tracked_threats(self) -> list[str]:
        return list(self.policy.get("llm_threats_tracked", []))

    def evaluate(self, implemented_controls: set[str]) -> dict[str, object]:
        coverage = [
            ControlCoverage(
                control=control,
                implemented=control in implemented_controls,
                evidence="present" if control in implemented_controls else "missing",
            )
            for control in self.required_controls()
        ]
        missing = [item.control for item in coverage if not item.implemented]
        return {
            "status": "pass" if not missing else "incomplete",
            "missing_controls": missing,
            "coverage": [item.__dict__ for item in coverage],
            "tracked_threat_count": len(self.tracked_threats()),
            "readiness": self.policy.get("readiness", "unknown"),
        }
