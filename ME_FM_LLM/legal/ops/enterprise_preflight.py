from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo
from legal.release.public_repo_readiness import PublicRepoReadinessAuditor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_policy(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / "configs" / "maine_enterprise_preflight_policy.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class EnterprisePreflightReport:
    status: str
    source_preflight_ready: bool
    networked_data_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    python_version: str
    platform: str
    external_dirs_planned: list[str] = field(default_factory=list)
    missing_scripts: list[str] = field(default_factory=list)
    missing_configs: list[str] = field(default_factory=list)
    repo_data_violations: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)
    public_release_readiness: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_preflight_ready": self.source_preflight_ready,
            "networked_data_ready": self.networked_data_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "python_version": self.python_version,
            "platform": self.platform,
            "external_dirs_planned": list(self.external_dirs_planned),
            "missing_scripts": list(self.missing_scripts),
            "missing_configs": list(self.missing_configs),
            "repo_data_violations": list(self.repo_data_violations),
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "next_commands": list(self.next_commands),
            "public_release_readiness": self.public_release_readiness,
        }


class EnterprisePreflightRunner:
    """Source and local-layout preflight for the Windows-first enterprise build path."""

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_policy(self.repo_root)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def run(self, *, create_external_dirs: bool = True) -> EnterprisePreflightReport:
        blockers: list[str] = []
        warnings: list[str] = []
        missing_scripts = [p for p in self.policy["required_scripts"] if not (self.repo_root / p).is_file()]
        missing_configs = [p for p in self.policy["required_configs"] if not (self.repo_root / p).is_file()]
        if missing_scripts:
            blockers.append("missing_required_scripts")
        if missing_configs:
            blockers.append("missing_required_configs")
        if sys.version_info < (3, 11):
            blockers.append("python_3_11_or_newer_required")
        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")

        repo_data_violations: list[str] = []
        for name in self.policy.get("source_repo_must_not_contain", []):
            candidate = self.repo_root / name
            if candidate.exists():
                repo_data_violations.append(candidate.relative_to(self.repo_root).as_posix())
        if repo_data_violations:
            blockers.append("runtime_or_data_store_present_in_source_repo")

        external_dirs: list[str] = []
        for name in self.policy.get("required_external_data_dirs", []):
            target = self.data_root / name
            external_dirs.append(str(target))
            if create_external_dirs:
                target.mkdir(parents=True, exist_ok=True)
        if not self.data_root.exists():
            warnings.append("data_root_not_created")

        public_report = PublicRepoReadinessAuditor(project_root=self.repo_root).audit().as_dict()
        if public_report["status"] != "pass":
            blockers.append("public_source_readiness_failed")

        source_ready = not blockers
        return EnterprisePreflightReport(
            status="pass" if source_ready else "fail",
            source_preflight_ready=source_ready,
            networked_data_ready=False,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            external_dirs_planned=external_dirs,
            missing_scripts=missing_scripts,
            missing_configs=missing_configs,
            repo_data_violations=repo_data_violations,
            blockers=blockers,
            warnings=warnings,
            next_commands=self.policy.get("networked_execution_commands", []),
            public_release_readiness=public_report,
        )

    def write(self, output_path: str | Path, *, create_external_dirs: bool = True) -> EnterprisePreflightReport:
        report = self.run(create_external_dirs=create_external_dirs)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report
