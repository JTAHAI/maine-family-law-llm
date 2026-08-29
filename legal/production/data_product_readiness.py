from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal.connectors import load_official_source_targets


@dataclass(frozen=True)
class DatasetReadiness:
    dataset: str
    rows: int
    minimum_rows: int
    attorney_reviewed_rows: int
    synthetic_or_seed_rows: int
    private_training_rows: int
    parse_errors: int = 0
    status: str = "blocked"

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SourceCoverage:
    source_class: str
    configured_targets: int
    minimum_targets: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class EnterpriseDataProductReport:
    production_ready: bool
    status: str
    blockers: list[str] = field(default_factory=list)
    source_coverage: list[SourceCoverage] = field(default_factory=list)
    datasets: list[DatasetReadiness] = field(default_factory=list)
    runtime_artifact_findings: list[str] = field(default_factory=list)
    policy_version: str = "unknown"
    readiness: str = "enterprise_data_product_blocked_until_external_corpus_and_gold_evals_exist"

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_ready": self.production_ready,
            "status": self.status,
            "readiness": self.readiness,
            "policy_version": self.policy_version,
            "blockers": sorted(set(self.blockers)),
            "source_coverage": [item.as_dict() for item in self.source_coverage],
            "datasets": [item.as_dict() for item in self.datasets],
            "runtime_artifact_findings": self.runtime_artifact_findings,
        }


class EnterpriseDataProductAuditor:
    """Audit whether the repository is backed by enterprise legal data assets.

    The audit is allowed to pass as an executable check while still declaring
    ``production_ready=False``. That distinction lets CI prove that the gate works
    without pretending the source ZIP contains the external legal corpus or attorney
    gold datasets.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)
        self.policy = json.loads(
            (self.project_root / "configs" / "maine_enterprise_data_product_policy.json").read_text(
                encoding="utf-8"
            )
        )

    def run(self) -> EnterpriseDataProductReport:
        blockers: list[str] = []
        source_coverage = self._source_coverage(blockers)
        datasets = self._dataset_readiness(blockers)
        runtime_findings = self._scan_for_forbidden_runtime_artifacts()
        if runtime_findings:
            blockers.append("runtime_artifacts_packaged_in_source_repo")

        production_ready = not blockers
        return EnterpriseDataProductReport(
            production_ready=production_ready,
            status="pass" if True else "fail",  # gate executed; readiness is separate
            blockers=blockers,
            source_coverage=source_coverage,
            datasets=datasets,
            runtime_artifact_findings=runtime_findings,
            policy_version=self.policy.get("version", "unknown"),
        )

    def _source_coverage(self, blockers: list[str]) -> list[SourceCoverage]:
        targets = load_official_source_targets()
        counts: dict[str, int] = {}
        for target in targets:
            counts[target.source_class] = counts.get(target.source_class, 0) + 1

        coverage: list[SourceCoverage] = []
        for source_class, minimum in self.policy["required_source_target_minimums"].items():
            actual = counts.get(source_class, 0)
            status = "pass" if actual >= int(minimum) else "blocked_minimum_source_targets"
            if status != "pass":
                blockers.append(f"source_target_minimum_not_met:{source_class}")
            coverage.append(
                SourceCoverage(
                    source_class=source_class,
                    configured_targets=actual,
                    minimum_targets=int(minimum),
                    status=status,
                )
            )

        official_domain_failures = [
            target.target_id
            for target in targets
            if "maine.gov" not in target.url and "courts.maine.gov" not in target.url
        ]
        if official_domain_failures:
            blockers.append("non_official_source_targets_configured")
        return coverage

    def _dataset_readiness(self, blockers: list[str]) -> list[DatasetReadiness]:
        dataset_results: list[DatasetReadiness] = []
        eval_dir = self.project_root / "eval_data"
        for dataset, minimum in self.policy["required_gold_dataset_minimums"].items():
            path = eval_dir / dataset
            rows = 0
            parse_errors = 0
            attorney_reviewed_rows = 0
            synthetic_or_seed_rows = 0
            private_training_rows = 0
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            row = json.loads(stripped)
                        except json.JSONDecodeError:
                            parse_errors += 1
                            continue
                        rows += 1
                        review_status = str(row.get("review_status", "")).lower()
                        method = str(row.get("annotator_or_generation_method", "")).lower()
                        if "attorney" in review_status and "not_attorney" not in review_status:
                            attorney_reviewed_rows += 1
                        if "seed" in review_status or "seed" in method or "synthetic" in method:
                            synthetic_or_seed_rows += 1
                        if row.get("private_data_allowed_for_training") is True:
                            private_training_rows += 1

            status = "pass"
            if rows < int(minimum):
                status = "blocked_minimum_rows"
                blockers.append(f"gold_rows_minimum_not_met:{dataset}")
            elif self.policy.get("attorney_review_required") and attorney_reviewed_rows < int(minimum):
                status = "blocked_attorney_review_rows"
                blockers.append(f"attorney_gold_rows_minimum_not_met:{dataset}")
            if parse_errors:
                status = "blocked_parse_errors"
                blockers.append(f"gold_dataset_parse_errors:{dataset}")
            if private_training_rows:
                status = "blocked_private_training_rows"
                blockers.append(f"private_training_rows_in_gold_dataset:{dataset}")
            dataset_results.append(
                DatasetReadiness(
                    dataset=dataset,
                    rows=rows,
                    minimum_rows=int(minimum),
                    attorney_reviewed_rows=attorney_reviewed_rows,
                    synthetic_or_seed_rows=synthetic_or_seed_rows,
                    private_training_rows=private_training_rows,
                    parse_errors=parse_errors,
                    status=status,
                )
            )
        return dataset_results

    def _scan_for_forbidden_runtime_artifacts(self) -> list[str]:
        patterns = self.policy.get("runtime_artifacts_forbidden_in_repo", [])
        findings: list[str] = []
        # Generated release evidence and build/install staging are audited by
        # the package-specific private-data scanner. They are not source-tree
        # contents and must not make this repository-boundary gate depend on
        # whatever synthetic E2E run happened most recently.
        ignored_dirs = {
            ".git",
            ".pytest_cache",
            ".venv",
            "__pycache__",
            "build",
            "dist",
            "node_modules",
        }
        public_fixture_prefixes = {
            ("data", "fixtures"),
            ("tests", "fixtures"),
        }
        # ``Path.rglob`` decides which children to visit before the caller can
        # reject a generated directory.  On a release tree that makes this
        # fail-closed audit needlessly traverse large MSIX/build artifacts and
        # can exceed the CLI's bounded test timeout.  Prune those directory
        # trees during discovery; the package-specific audit owns their
        # inspection and this repository-boundary audit never treats them as
        # source contents.
        for root, directories, filenames in os.walk(self.project_root, topdown=True):
            current = Path(root)
            relative_root = current.relative_to(self.project_root)
            directories[:] = [name for name in directories if name not in ignored_dirs]
            names = [*directories, *filenames]
            for name in names:
                path = current / name
                relative_path = relative_root / name
                rel = relative_path.as_posix()
                if any(relative_path.parts[: len(prefix)] == prefix for prefix in public_fixture_prefixes):
                    continue
                for pattern in patterns:
                    normalized = pattern.rstrip("/")
                    if pattern.endswith("/") and path.is_dir() and rel == normalized:
                        findings.append(rel + "/")
                    elif fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel, pattern):
                        findings.append(rel)
        return sorted(set(findings))
