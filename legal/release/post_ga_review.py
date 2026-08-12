from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal.evals.gold_pack import GoldEvalPackAuditor
from legal.production.authority_build import AuthorityBuildAuditor
from legal.production.release_gates import ReleaseGateRunner
from legal.release.release_manifest import ReleaseManifest


@dataclass(frozen=True)
class BuildPathStage:
    stage_id: str
    priority: str
    title: str
    owner_lane: str
    commands: list[str] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)
    status: str = "pending_external_execution"

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "priority": self.priority,
            "title": self.title,
            "owner_lane": self.owner_lane,
            "commands": list(self.commands),
            "exit_criteria": list(self.exit_criteria),
            "status": self.status,
        }


@dataclass(frozen=True)
class PostGARepoReviewReport:
    status: str
    production_ready: bool
    production_status: str
    project_root: str
    data_root: str
    eval_root: str
    numbered_pass_foundations_complete: bool
    single_pass_log_present: bool
    only_one_pass_txt_file: bool
    fixture_evidence_detected: bool
    source_repo_clean: bool
    blockers: list[str] = field(default_factory=list)
    build_path: list[dict[str, Any]] = field(default_factory=list)
    audit_summary: dict[str, Any] = field(default_factory=dict)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "production_ready": self.production_ready,
            "production_status": self.production_status,
            "project_root": self.project_root,
            "data_root": self.data_root,
            "eval_root": self.eval_root,
            "numbered_pass_foundations_complete": self.numbered_pass_foundations_complete,
            "single_pass_log_present": self.single_pass_log_present,
            "only_one_pass_txt_file": self.only_one_pass_txt_file,
            "fixture_evidence_detected": self.fixture_evidence_detected,
            "source_repo_clean": self.source_repo_clean,
            "blockers": sorted(set(self.blockers)),
            "build_path": self.build_path,
            "audit_summary": self.audit_summary,
            "interpretation": self.interpretation,
        }


class PostGARepoReviewer:
    """Review the post-Pass-51 repo and produce the real build path.

    The numbered roadmap can be complete as source-code controls while the legal
    product remains blocked for production. This reviewer makes that distinction
    explicit so fixture evidence can never be confused with live legal-data,
    attorney-review, security, pilot, or signoff evidence.
    """

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path = "/mnt/data/maine-family-law-llm-data",
        eval_root: str | Path | None = None,
        policy_path: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.project_root / "eval_data"
        self.policy_path = Path(policy_path) if policy_path else self.project_root / "configs" / "maine_post_ga_build_path.json"
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))

    def review(self, *, output_path: str | Path | None = None) -> PostGARepoReviewReport:
        pass_log = self.project_root / "PASS_CHANGES.txt"
        pass_number = 0
        if pass_log.exists():
            match = re.search(
                r"Current completed implementation pass number:\s*(\d+)",
                pass_log.read_text(encoding="utf-8"),
            )
            if match:
                pass_number = int(match.group(1))
        numbered_complete = pass_number >= 51
        txt_files = [path for path in self.project_root.rglob("*.txt") if self._is_repo_file(path)]
        only_one_pass_txt = len([path for path in txt_files if "pass" in path.name.lower()]) == 1
        single_pass_log_present = pass_log.exists() and pass_log in txt_files
        fixture_detected = self._fixture_evidence_detected()
        source_manifest = ReleaseManifest(project_root=self.project_root, version="post-ga-review").generate()
        source_repo_clean = not source_manifest["contains_private_data"] and not source_manifest["runtime_state_packaged"]

        authority_report = AuthorityBuildAuditor(project_root=self.project_root, data_root=self.data_root).run()
        gold_report = GoldEvalPackAuditor(project_root=self.project_root, eval_root=self.eval_root).run()
        release_report = ReleaseGateRunner().evaluate({})

        blockers: list[str] = []
        if not numbered_complete:
            blockers.append("source_foundations_not_complete_through_pass_51")
        if not single_pass_log_present:
            blockers.append("PASS_CHANGES_txt_missing")
        if not only_one_pass_txt:
            blockers.append("more_than_one_pass_txt_file_present")
        if not source_repo_clean:
            blockers.append("source_repo_contains_private_or_runtime_artifacts")
        if fixture_detected:
            blockers.append("fixture_evidence_must_be_replaced_before_real_ga")
        blockers.extend(f"authority:{item}" for item in authority_report.blockers)
        blockers.extend(f"gold_eval:{item}" for item in gold_report.blockers)
        blockers.extend(f"release_metric:{item}" for item in release_report.blockers)

        production_ready = (
            numbered_complete
            and source_repo_clean
            and not fixture_detected
            and authority_report.production_ready
            and gold_report.production_ready
            and release_report.release_allowed
        )
        build_path = [BuildPathStage(**stage).as_dict() for stage in self.policy.get("build_path", [])]
        report = PostGARepoReviewReport(
            status="pass",
            production_ready=production_ready,
            production_status="production_ready" if production_ready else "blocked_real_build_path_required",
            project_root=str(self.project_root),
            data_root=str(self.data_root),
            eval_root=str(self.eval_root),
            numbered_pass_foundations_complete=numbered_complete,
            single_pass_log_present=single_pass_log_present,
            only_one_pass_txt_file=only_one_pass_txt,
            fixture_evidence_detected=fixture_detected,
            source_repo_clean=source_repo_clean,
            blockers=blockers,
            build_path=build_path,
            audit_summary={
                "authority_build": {
                    "production_ready": authority_report.production_ready,
                    "readiness": authority_report.readiness,
                    "total_records": authority_report.total_records,
                    "blocker_count": len(authority_report.blockers),
                },
                "gold_eval_pack": {
                    "production_ready": gold_report.production_ready,
                    "readiness": gold_report.readiness,
                    "dataset_count": len(gold_report.datasets),
                    "blocker_count": len(gold_report.blockers),
                },
                "release_gates": {
                    "release_allowed": release_report.release_allowed,
                    "readiness": release_report.readiness,
                    "required_metric_count": len(release_report.required_metrics),
                    "blocker_count": len(release_report.blockers),
                },
            },
            interpretation=(
                "All numbered pass source-control foundations are present, but this repo is not a real production GA legal product until the external build path is executed and fixture evidence is replaced with live official Maine authority, attorney-reviewed gold data, measured release metrics, pilot/security evidence, and accountable signoffs."
            ),
        )
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _is_repo_file(self, path: Path) -> bool:
        parts = set(path.relative_to(self.project_root).parts)
        ignored = {".git", ".pytest_cache", ".ruff_cache", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".eggs"}
        return not bool(parts & ignored) and not any(part.endswith(".egg-info") for part in parts)

    def _fixture_evidence_detected(self) -> bool:
        needles = ("sha256:fixture", "build_ga_control_fixture", "build_approved_signoff_fixture")
        for path in [self.project_root / "legal" / "release" / "ga_release.py", self.project_root / "scripts" / "run-ga-release-evidence.py"]:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                if any(needle in text for needle in needles):
                    return True
        return False
