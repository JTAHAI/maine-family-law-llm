from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.ops.networked_source_gate import NetworkedSourceGateAuditor
from legal.ops.operator_test_battery import OperatorTestBatteryAuditor
from legal.ops.production_promotion import ProductionPromotionGateAuditor
from legal.release.public_repo_readiness import PublicRepoReadinessAuditor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_policy(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / "configs" / "maine_operator_handoff_policy.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class OperatorHandoffBundleReport:
    status: str
    repo_root: str
    data_root: str
    generated_at: str
    python_version: str
    platform: str
    missing_operator_scripts: list[str] = field(default_factory=list)
    script_hashes: dict[str, str] = field(default_factory=dict)
    operator_test_battery_status: str = "unknown"
    networked_source_gate_status: str = "unknown"
    production_promotion_gate_status: str = "unknown"
    public_repo_readiness_status: str = "unknown"
    recommended_first_commands: list[str] = field(default_factory=list)
    known_non_production_blockers: list[str] = field(default_factory=list)
    bundle: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "python_version": self.python_version,
            "platform": self.platform,
            "missing_operator_scripts": list(self.missing_operator_scripts),
            "script_hashes": dict(self.script_hashes),
            "operator_test_battery_status": self.operator_test_battery_status,
            "networked_source_gate_status": self.networked_source_gate_status,
            "production_promotion_gate_status": self.production_promotion_gate_status,
            "public_repo_readiness_status": self.public_repo_readiness_status,
            "recommended_first_commands": list(self.recommended_first_commands),
            "known_non_production_blockers": list(self.known_non_production_blockers),
            "bundle": self.bundle,
        }


class OperatorHandoffBundleBuilder:
    """Build a single JSON handoff file for the next human operator.

    This is source-safe and does not collect legal data into the repo. It fingerprints the
    operator scripts, embeds status summaries, and gives the exact next Windows commands.
    """

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_policy(self.repo_root)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def build(self) -> OperatorHandoffBundleReport:
        required_scripts = list(self.policy.get("required_operator_scripts", []))
        missing = [rel for rel in required_scripts if not (self.repo_root / rel).is_file()]
        hashes = {
            rel: _sha256(self.repo_root / rel)
            for rel in required_scripts
            if (self.repo_root / rel).is_file()
        }

        operator = OperatorTestBatteryAuditor(self.repo_root, self.data_root).audit(
            create_external_dirs=False,
            write_probe=False,
        ).as_dict()
        networked = NetworkedSourceGateAuditor(self.repo_root, self.data_root).audit().as_dict()
        public_ready = PublicRepoReadinessAuditor(self.repo_root).audit().as_dict()
        promotion = ProductionPromotionGateAuditor(self.repo_root, self.data_root).audit().as_dict()

        first_commands = [
            "cd C:\\dev\\ME_FM_LLM",
            "python scripts\\run-reboot-safe-healthcheck.py",
            "python scripts\\run-operator-test-battery.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python -m pytest -q",
            "python scripts\\run-networked-source-gate.py --data-root C:\\dev\\ME_FM_LLM_data --allow-fail-report",
            "python scripts\\run-production-promotion-gate.py --data-root C:\\dev\\ME_FM_LLM_data --allow-fail-report",
        ]
        bundle = {
            "environment": {
                "expected_windows_repo_root": self.policy["default_windows_repo_root"],
                "expected_windows_data_root": self.policy["default_windows_data_root"],
                "actual_repo_root": str(self.repo_root),
                "actual_data_root": str(self.data_root),
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
            },
            "source_tree": {
                "public_repo_readiness": public_ready,
                "operator_script_hashes": hashes,
                "missing_operator_scripts": missing,
                "only_pass_log_txt_rule": "PASS_CHANGES.txt is the only pass log text file in the repo.",
            },
            "operator_commands": {
                "first_commands_after_unzip_or_reboot": first_commands,
                "networked_collection_commands": networked.get("next_commands", []),
                "production_promotion_commands": promotion.get("next_commands", []),
            },
            "networked_source_gate": networked,
            "production_promotion_gate": promotion,
            "local_operator_test_battery": operator,
            "public_github_staging": {
                "ready_to_stage_source": public_ready.get("public_source_ready") is True,
                "do_not_claim_legal_production_ready_from_fixture_tests": True,
            },
            "known_non_production_blockers": list(self.policy.get("known_non_production_blockers", [])),
        }
        status = "pass" if not missing and operator.get("status") == "pass" and public_ready.get("status") == "pass" else "fail"
        return OperatorHandoffBundleReport(
            status=status,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            missing_operator_scripts=missing,
            script_hashes=hashes,
            operator_test_battery_status=str(operator.get("status", "unknown")),
            networked_source_gate_status=str(networked.get("status", "unknown")),
            production_promotion_gate_status=str(promotion.get("status", "unknown")),
            public_repo_readiness_status=str(public_ready.get("status", "unknown")),
            recommended_first_commands=first_commands,
            known_non_production_blockers=list(self.policy.get("known_non_production_blockers", [])),
            bundle=bundle,
        )

    def write(self, output_path: str | Path) -> OperatorHandoffBundleReport:
        report = self.build()
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def build_operator_handoff_bundle(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    return OperatorHandoffBundleBuilder(project_root, data_root).build().as_dict()
