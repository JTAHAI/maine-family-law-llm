from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo
from legal.ops.enterprise_acceptance import EnterpriseAcceptanceAuditor
from legal.ops.enterprise_preflight import EnterprisePreflightRunner
from legal.ops.reboot_recovery import RebootRecoveryAuditor
from legal.ops.supply_chain import SupplyChainAuditor
from legal.release.public_repo_readiness import PublicRepoReadinessAuditor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_policy(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / "configs" / "maine_operator_test_battery_policy.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class OperatorTestBatteryReport:
    status: str
    ready_for_operator_local_test: bool
    production_legal_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    python_version: str
    platform: str
    missing_required_repo_files: list[str] = field(default_factory=list)
    external_dirs_checked: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reboot_recovery: dict[str, Any] = field(default_factory=dict)
    enterprise_preflight: dict[str, Any] = field(default_factory=dict)
    public_repo_readiness: dict[str, Any] = field(default_factory=dict)
    enterprise_acceptance: dict[str, Any] = field(default_factory=dict)
    supply_chain_summary: dict[str, Any] = field(default_factory=dict)
    local_operator_commands: list[str] = field(default_factory=list)
    networked_authority_commands: list[str] = field(default_factory=list)
    production_legal_readiness_blockers: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready_for_operator_local_test": self.ready_for_operator_local_test,
            "production_legal_ready": self.production_legal_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "python_version": self.python_version,
            "platform": self.platform,
            "missing_required_repo_files": list(self.missing_required_repo_files),
            "external_dirs_checked": list(self.external_dirs_checked),
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "reboot_recovery": self.reboot_recovery,
            "enterprise_preflight": self.enterprise_preflight,
            "public_repo_readiness": self.public_repo_readiness,
            "enterprise_acceptance": self.enterprise_acceptance,
            "supply_chain_summary": self.supply_chain_summary,
            "local_operator_commands": list(self.local_operator_commands),
            "networked_authority_commands": list(self.networked_authority_commands),
            "production_legal_readiness_blockers": list(self.production_legal_readiness_blockers),
            "interpretation": self.interpretation,
        }


class OperatorTestBatteryAuditor:
    """Runs a fast, deterministic operator acceptance battery for the source tree.

    The battery is intentionally source/local-test oriented. It does not certify legal
    production readiness because that requires networked official authority collection,
    attorney-reviewed gold data, measured metrics, pilot/security evidence, and signoffs.
    """

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_policy(self.repo_root)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def audit(self, *, create_external_dirs: bool = True, write_probe: bool = True) -> OperatorTestBatteryReport:
        blockers: list[str] = []
        warnings: list[str] = []

        missing_files = [
            item for item in self.policy.get("required_repo_files", []) if not (self.repo_root / item).is_file()
        ]
        if missing_files:
            blockers.append("missing_required_repo_files")

        if sys.version_info < (3, 11):
            blockers.append("python_3_11_or_newer_required")
        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")

        external_dirs: list[str] = []
        for item in self.policy.get("external_data_dirs", []):
            target = self.data_root / item
            external_dirs.append(str(target))
            if create_external_dirs:
                target.mkdir(parents=True, exist_ok=True)

        reboot = RebootRecoveryAuditor(self.repo_root, self.data_root).audit(
            create_external_dirs=create_external_dirs,
            write_probe=write_probe,
        ).as_dict()
        if reboot["status"] != "pass":
            blockers.append("reboot_recovery_failed")

        preflight = EnterprisePreflightRunner(self.repo_root, self.data_root).run(
            create_external_dirs=create_external_dirs,
        ).as_dict()
        if preflight["status"] != "pass":
            blockers.append("enterprise_preflight_failed")

        public_ready = PublicRepoReadinessAuditor(self.repo_root).audit().as_dict()
        if public_ready["status"] != "pass":
            blockers.append("public_repo_readiness_failed")

        acceptance = EnterpriseAcceptanceAuditor(self.repo_root).audit().as_dict()
        if acceptance["status"] != "pass":
            blockers.append("enterprise_acceptance_failed")
        if acceptance.get("production_legal_ready") is not False:
            blockers.append("operator_battery_must_not_mark_production_legal_ready")

        supply_chain = SupplyChainAuditor(self.repo_root).audit(write_sbom=False).as_dict()
        supply_summary = {k: v for k, v in supply_chain.items() if k != "sbom"}
        if supply_chain["status"] != "pass":
            blockers.append("supply_chain_failed")

        if not blockers:
            warnings.append("operator_local_test_ready_not_production_legal_ready")
            warnings.append("run_networked_authority_commands_before_real_legal_validation")

        ready = not blockers
        return OperatorTestBatteryReport(
            status="pass" if ready else "fail",
            ready_for_operator_local_test=ready,
            production_legal_ready=False,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            missing_required_repo_files=missing_files,
            external_dirs_checked=external_dirs,
            blockers=blockers,
            warnings=warnings,
            reboot_recovery=reboot,
            enterprise_preflight=preflight,
            public_repo_readiness=public_ready,
            enterprise_acceptance=acceptance,
            supply_chain_summary=supply_summary,
            local_operator_commands=self.policy.get("local_operator_commands", []),
            networked_authority_commands=self.policy.get("networked_authority_commands", []),
            production_legal_readiness_blockers=self.policy.get("production_legal_readiness_blockers", []),
            interpretation=(
                "Operator test battery pass means the source tree is ready for local fixture/source testing and "
                "public-repo hygiene checks. It is not a certification of legal production readiness."
            ),
        )

    def write(self, output_path: str | Path, **kwargs: Any) -> OperatorTestBatteryReport:
        report = self.audit(**kwargs)
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def run_operator_test_battery(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
    *,
    create_external_dirs: bool = True,
    write_probe: bool = True,
) -> dict[str, Any]:
    return OperatorTestBatteryAuditor(project_root, data_root).audit(
        create_external_dirs=create_external_dirs,
        write_probe=write_probe,
    ).as_dict()
