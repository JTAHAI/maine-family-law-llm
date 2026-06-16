from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.ops.enterprise_acceptance import EnterpriseAcceptanceAuditor, ReleaseLockfileBuilder
from legal.ops.enterprise_preflight import EnterprisePreflightRunner
from legal.ops.supply_chain import SupplyChainAuditor
from legal.release.public_repo_readiness import PublicRepoReadinessAuditor
from legal.resources.offline_validation_pack import OfflineValidationPackBuilder


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_policy(project_root: Path) -> dict[str, Any]:
    return json.loads(
        (project_root / "configs" / "maine_local_test_readiness_policy.json").read_text(
            encoding="utf-8"
        )
    )


def _run_command(command: list[str], cwd: Path, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "timed_out": False,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "returncode": 124,
            "timed_out": True,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


@dataclass(frozen=True)
class LocalTestReadinessReport:
    status: str
    ready_to_test_locally: bool
    public_github_source_ready: bool
    production_legal_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    pytest: dict[str, Any] = field(default_factory=dict)
    public_source_readiness: dict[str, Any] = field(default_factory=dict)
    enterprise_preflight: dict[str, Any] = field(default_factory=dict)
    offline_validation_pack: dict[str, Any] = field(default_factory=dict)
    release_lock_audit: dict[str, Any] = field(default_factory=dict)
    enterprise_acceptance: dict[str, Any] = field(default_factory=dict)
    supply_chain_summary: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_windows_test_commands: list[str] = field(default_factory=list)
    production_legal_readiness_required_external_evidence: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready_to_test_locally": self.ready_to_test_locally,
            "public_github_source_ready": self.public_github_source_ready,
            "production_legal_ready": self.production_legal_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "pytest": self.pytest,
            "public_source_readiness": self.public_source_readiness,
            "enterprise_preflight": self.enterprise_preflight,
            "offline_validation_pack": self.offline_validation_pack,
            "release_lock_audit": self.release_lock_audit,
            "enterprise_acceptance": self.enterprise_acceptance,
            "supply_chain_summary": self.supply_chain_summary,
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "recommended_windows_test_commands": list(self.recommended_windows_test_commands),
            "production_legal_readiness_required_external_evidence": list(
                self.production_legal_readiness_required_external_evidence
            ),
            "interpretation": self.interpretation,
        }


class LocalTestReadinessAuditor:
    """Certify whether the source tree is ready for local testing.

    This intentionally distinguishes local source/test readiness from production legal readiness.
    Production use still requires real external Maine authority, attorney-reviewed eval data,
    measured metrics, pilot/security evidence, and owner signoffs.
    """

    def __init__(self, project_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.policy = _load_policy(self.project_root)
        self.data_root = Path(data_root or self.policy["windows_data_root"]).expanduser().resolve()

    def audit(
        self,
        *,
        run_pytest: bool = True,
        include_quality_checks: bool = False,
        timeout_seconds: int = 180,
    ) -> LocalTestReadinessReport:
        blockers: list[str] = []
        warnings: list[str] = []

        pytest_result: dict[str, Any] = {"status": "skipped", "returncode": 0, "timed_out": False}
        if run_pytest:
            pytest_result = _run_command(
                [sys.executable, "-m", "pytest", "-q"],
                self.project_root,
                timeout_seconds=timeout_seconds,
            )
            if pytest_result["returncode"] != 0:
                blockers.append("pytest_failed_or_timed_out")

        if include_quality_checks:
            quality_result = _run_command(
                [sys.executable, "scripts/run-quality-checks.py"],
                self.project_root,
                timeout_seconds=max(timeout_seconds, 300),
            )
            pytest_result["quality_checks"] = quality_result
            if quality_result["returncode"] != 0:
                blockers.append("quality_checks_failed_or_timed_out")

        public_report = PublicRepoReadinessAuditor(self.project_root).audit().as_dict()
        if public_report["status"] != "pass":
            blockers.append("public_source_readiness_failed")

        preflight_report = (
            EnterprisePreflightRunner(self.project_root, self.data_root)
            .run(create_external_dirs=True)
            .as_dict()
        )
        if preflight_report["status"] != "pass":
            blockers.append("enterprise_preflight_failed")

        fixture_root = self.data_root / "_local_test_readiness_offline_fixture"
        offline_pack = OfflineValidationPackBuilder(fixture_root).build().as_dict()
        if offline_pack["status"] != "pass":
            blockers.append("offline_validation_pack_failed")
        if offline_pack.get("fixture_only") is not True:
            blockers.append("offline_validation_pack_must_remain_fixture_only")

        evidence_root = self.data_root / "_local_test_readiness_evidence"
        evidence_root.mkdir(parents=True, exist_ok=True)

        acceptance = EnterpriseAcceptanceAuditor(self.project_root).write(
            evidence_root / "enterprise_acceptance_evidence.json"
        ).as_dict()
        if acceptance["status"] != "pass":
            blockers.append("enterprise_acceptance_failed")
        if acceptance.get("production_legal_ready") is not False:
            blockers.append("source_only_acceptance_must_not_mark_production_legal_ready")

        supply_chain = SupplyChainAuditor(self.project_root).audit(
            write_sbom=True,
            output_path=evidence_root / "source_sbom.json",
        ).as_dict()
        supply_summary = {k: v for k, v in supply_chain.items() if k != "sbom"}
        if supply_chain["status"] != "pass":
            blockers.append("supply_chain_audit_failed")

        # Build the release lock after generated source-evidence files are refreshed so the
        # lockfile audit reflects the actual staged source tree.
        lock_path = evidence_root / "source_release_lock.json"
        ReleaseLockfileBuilder(self.project_root).write(lock_path)
        lock_audit = ReleaseLockfileBuilder(self.project_root).audit(lock_path).as_dict()
        if lock_audit["status"] != "pass":
            blockers.append("release_lock_audit_failed")

        if not blockers and acceptance.get("production_legal_ready") is False:
            warnings.append("ready_for_local_testing_not_production_legal_use")
            warnings.append("networked_resource_collection_still_required_for_real_authority")

        ready_to_test = not blockers
        public_ready = public_report.get("public_source_ready") is True
        production_ready = acceptance.get("production_legal_ready") is True
        return LocalTestReadinessReport(
            status="pass" if ready_to_test else "fail",
            ready_to_test_locally=ready_to_test,
            public_github_source_ready=public_ready,
            production_legal_ready=production_ready,
            repo_root=str(self.project_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            pytest=pytest_result,
            public_source_readiness=public_report,
            enterprise_preflight=preflight_report,
            offline_validation_pack=offline_pack,
            release_lock_audit=lock_audit,
            enterprise_acceptance=acceptance,
            supply_chain_summary=supply_summary,
            blockers=blockers,
            warnings=warnings,
            recommended_windows_test_commands=self.policy.get(
                "recommended_windows_test_commands", []
            ),
            production_legal_readiness_required_external_evidence=self.policy.get(
                "production_legal_readiness_required_external_evidence", []
            ),
            interpretation=(
                "Ready to test locally means the source tree, scripts, audits, lockfile, "
                "offline fixture pack, public-source hygiene, and external-data-root "
                "preflight are runnable. It does not mean the product is ready for legal "
                "production use; production legal readiness remains blocked until real "
                "external authority, attorney-reviewed evals, measured metrics, "
                "pilot/security evidence, and signoffs are attached."
            ),
        )

    def write(self, output_path: str | Path, **kwargs: Any) -> LocalTestReadinessReport:
        report = self.audit(**kwargs)
        path = Path(output_path)
        if not path.is_absolute():
            path = self.project_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def run_local_test_readiness(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
    *,
    run_pytest: bool = True,
    include_quality_checks: bool = False,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    return LocalTestReadinessAuditor(project_root, data_root).audit(
        run_pytest=run_pytest,
        include_quality_checks=include_quality_checks,
        timeout_seconds=timeout_seconds,
    ).as_dict()
