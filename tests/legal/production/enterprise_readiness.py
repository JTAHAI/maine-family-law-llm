from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal.evals.gold_pack import GoldEvalPackAuditor, GoldEvalPackReport
from legal.production.authority_build import AuthorityBuildAuditor, AuthorityBuildReport
from legal.production.data_product_readiness import EnterpriseDataProductAuditor, EnterpriseDataProductReport
from legal.production.release_gates import ReleaseGateRunner, ReleaseMetric, ReleaseReadinessReport


@dataclass
class EnterpriseReadinessReport:
    production_ready: bool
    status: str
    repo_data_product: EnterpriseDataProductReport
    authority_build: AuthorityBuildReport
    gold_eval_pack: GoldEvalPackReport
    release_gates: ReleaseReadinessReport
    blockers: list[str] = field(default_factory=list)
    readiness: str = "enterprise_blocked_until_corpus_gold_release_security_and_pilot_are_complete"

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_ready": self.production_ready,
            "status": self.status,
            "readiness": self.readiness,
            "blockers": sorted(set(self.blockers)),
            "repo_data_product": self.repo_data_product.as_dict(),
            "authority_build": self.authority_build.as_dict(),
            "gold_eval_pack": self.gold_eval_pack.as_dict(),
            "release_gates": self.release_gates.as_dict(),
        }


class EnterpriseReadinessAuditor:
    """Combine repo, external authority, gold-eval, and release-gate checks."""

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path,
        eval_root: str | Path | None = None,
        release_metrics: dict[str, ReleaseMetric | dict[str, Any] | float | None] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else None
        self.release_metrics = release_metrics or {}

    def run(self) -> EnterpriseReadinessReport:
        repo_report = EnterpriseDataProductAuditor(self.project_root).run()
        authority_report = AuthorityBuildAuditor(
            project_root=self.project_root,
            data_root=self.data_root,
        ).run()
        gold_report = GoldEvalPackAuditor(
            project_root=self.project_root,
            eval_root=self.eval_root,
        ).run()
        release_report = ReleaseGateRunner().evaluate(self.release_metrics)
        blockers = (
            [f"repo:{blocker}" for blocker in repo_report.blockers]
            + [f"authority:{blocker}" for blocker in authority_report.blockers]
            + [f"gold_eval:{blocker}" for blocker in gold_report.blockers]
            + [f"release_gate:{blocker}" for blocker in release_report.blockers]
        )
        production_ready = (
            repo_report.production_ready
            and authority_report.production_ready
            and gold_report.production_ready
            and release_report.release_allowed
        )
        return EnterpriseReadinessReport(
            production_ready=production_ready,
            status="pass",
            repo_data_product=repo_report,
            authority_build=authority_report,
            gold_eval_pack=gold_report,
            release_gates=release_report,
            blockers=sorted(set(blockers)),
            readiness=(
                "enterprise_release_ready"
                if production_ready
                else "enterprise_blocked_until_corpus_gold_release_security_and_pilot_are_complete"
            ),
        )
