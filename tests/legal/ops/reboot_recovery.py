from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_policy(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / "configs" / "maine_reboot_recovery_policy.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RebootRecoveryReport:
    status: str
    reboot_safe_for_local_testing: bool
    production_legal_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    python_version: str
    platform: str
    required_files_missing: list[str] = field(default_factory=list)
    forbidden_source_paths_present: list[str] = field(default_factory=list)
    external_dirs_checked: list[str] = field(default_factory=list)
    write_probe_path: str | None = None
    write_probe_ok: bool = False
    txt_files: list[str] = field(default_factory=list)
    one_pass_log_only: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    after_reboot_windows_commands: list[str] = field(default_factory=list)
    networked_collection_commands: list[str] = field(default_factory=list)
    production_legal_readiness_remains_blocked_until: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reboot_safe_for_local_testing": self.reboot_safe_for_local_testing,
            "production_legal_ready": self.production_legal_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "python_version": self.python_version,
            "platform": self.platform,
            "required_files_missing": list(self.required_files_missing),
            "forbidden_source_paths_present": list(self.forbidden_source_paths_present),
            "external_dirs_checked": list(self.external_dirs_checked),
            "write_probe_path": self.write_probe_path,
            "write_probe_ok": self.write_probe_ok,
            "txt_files": list(self.txt_files),
            "one_pass_log_only": self.one_pass_log_only,
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "after_reboot_windows_commands": list(self.after_reboot_windows_commands),
            "networked_collection_commands": list(self.networked_collection_commands),
            "production_legal_readiness_remains_blocked_until": list(
                self.production_legal_readiness_remains_blocked_until
            ),
            "interpretation": self.interpretation,
        }


class RebootRecoveryAuditor:
    """Checks that a local enterprise test tree can be resumed safely after a reboot."""

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_policy(self.repo_root)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def audit(self, *, create_external_dirs: bool = True, write_probe: bool = True) -> RebootRecoveryReport:
        blockers: list[str] = []
        warnings: list[str] = []

        required_files_missing = [
            item for item in self.policy.get("required_repo_files", []) if not (self.repo_root / item).is_file()
        ]
        if required_files_missing:
            blockers.append("missing_required_repo_files")

        if sys.version_info < (3, 11):
            blockers.append("python_3_11_or_newer_required")

        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")

        forbidden_source_paths_present: list[str] = []
        for item in self.policy.get("source_repo_must_not_contain", []):
            candidate = self.repo_root / item
            if candidate.exists():
                forbidden_source_paths_present.append(candidate.relative_to(self.repo_root).as_posix())
        if forbidden_source_paths_present:
            blockers.append("runtime_or_data_paths_present_in_source_repo")

        ignored_txt_parts = {
            ".git",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".eggs",
        }
        txt_files = sorted(
            path.relative_to(self.repo_root).as_posix()
            for path in self.repo_root.rglob("*.txt")
            if not any(
                part in ignored_txt_parts or part.endswith(".egg-info")
                for part in path.relative_to(self.repo_root).parts
            )
        )
        one_pass_log_only = txt_files == ["PASS_CHANGES.txt"]
        if not one_pass_log_only:
            blockers.append("pass_log_txt_discipline_failed")

        external_dirs_checked: list[str] = []
        for item in self.policy.get("required_external_data_dirs", []):
            target = self.data_root / item
            external_dirs_checked.append(str(target))
            if create_external_dirs:
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                warnings.append(f"external_dir_missing:{item}")

        write_probe_path: str | None = None
        write_probe_ok = False
        if write_probe:
            try:
                self.data_root.mkdir(parents=True, exist_ok=True)
                probe = self.data_root / "runtime" / ".reboot_safe_write_probe.json"
                probe.parent.mkdir(parents=True, exist_ok=True)
                probe.write_text(json.dumps({"generated_at": _utc_now(), "purpose": "write_probe"}), encoding="utf-8")
                write_probe_ok = json.loads(probe.read_text(encoding="utf-8"))["purpose"] == "write_probe"
                probe.unlink(missing_ok=True)
                write_probe_path = str(probe)
            except Exception as exc:  # pragma: no cover - defensive filesystem path
                blockers.append("external_data_root_write_probe_failed")
                warnings.append(f"write_probe_error:{type(exc).__name__}:{exc}")
        else:
            write_probe_ok = True

        if not write_probe_ok:
            blockers.append("external_data_root_not_writable")

        if not blockers:
            warnings.append("ready_to_resume_after_reboot_for_local_source_fixture_testing")
            warnings.append("production_legal_use_still_requires_networked_authority_and_real_signoffs")

        reboot_safe = not blockers
        return RebootRecoveryReport(
            status="pass" if reboot_safe else "fail",
            reboot_safe_for_local_testing=reboot_safe,
            production_legal_ready=False,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            required_files_missing=required_files_missing,
            forbidden_source_paths_present=forbidden_source_paths_present,
            external_dirs_checked=external_dirs_checked,
            write_probe_path=write_probe_path,
            write_probe_ok=write_probe_ok,
            txt_files=txt_files,
            one_pass_log_only=one_pass_log_only,
            blockers=blockers,
            warnings=warnings,
            after_reboot_windows_commands=self.policy.get("after_reboot_windows_commands", []),
            networked_collection_commands=self.policy.get("networked_collection_commands", []),
            production_legal_readiness_remains_blocked_until=self.policy.get(
                "production_legal_readiness_remains_blocked_until", []
            ),
            interpretation=(
                "Reboot-safe means the source tree, required scripts/configs, external data-root layout, "
                "write permissions, and PASS_CHANGES-only TXT discipline are valid for local testing. It does not "
                "mean legal production readiness; live official authority, attorney-reviewed evals, real metrics, "
                "pilot/security evidence, and signoffs are still required."
            ),
        )

    def write(self, output_path: str | Path, **kwargs: Any) -> RebootRecoveryReport:
        report = self.audit(**kwargs)
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def run_reboot_recovery_healthcheck(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
    *,
    create_external_dirs: bool = True,
    write_probe: bool = True,
) -> dict[str, Any]:
    return RebootRecoveryAuditor(project_root, data_root).audit(
        create_external_dirs=create_external_dirs,
        write_probe=write_probe,
    ).as_dict()
