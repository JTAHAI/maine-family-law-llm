from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoldDatasetFinding:
    dataset: str
    row_number: int | None
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class GoldDatasetStatus:
    dataset: str
    rows: int
    minimum_rows: int
    attorney_reviewed_rows: int
    synthetic_or_seed_rows: int
    private_training_rows: int
    rows_missing_required_fields: int
    parse_errors: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class GoldEvalPackReport:
    production_ready: bool
    status: str
    eval_root: str
    datasets: list[GoldDatasetStatus] = field(default_factory=list)
    findings: list[GoldDatasetFinding] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    policy_version: str = "unknown"
    readiness: str = "gold_eval_pack_blocked_until_attorney_reviewed_jsonl_meets_minimums"

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_ready": self.production_ready,
            "status": self.status,
            "readiness": self.readiness,
            "policy_version": self.policy_version,
            "eval_root": self.eval_root,
            "datasets": [item.as_dict() for item in self.datasets],
            "findings": [item.as_dict() for item in self.findings],
            "blockers": sorted(set(self.blockers)),
        }


class GoldEvalPackAuditor:
    """Validate attorney-reviewed gold datasets for release gates."""

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        eval_root: str | Path | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.project_root / "eval_data"
        self.policy = policy or json.loads(
            (self.project_root / "configs" / "maine_gold_eval_pack_policy.json").read_text(
                encoding="utf-8"
            )
        )

    def run(self) -> GoldEvalPackReport:
        findings: list[GoldDatasetFinding] = []
        blockers: list[str] = []
        statuses: list[GoldDatasetStatus] = []
        for dataset, minimum in self.policy.get("required_gold_dataset_minimums", {}).items():
            statuses.append(self._audit_dataset(dataset, int(minimum), findings, blockers))

        production_ready = not blockers
        return GoldEvalPackReport(
            production_ready=production_ready,
            status="pass",
            eval_root=str(self.eval_root),
            datasets=statuses,
            findings=findings,
            blockers=sorted(set(blockers)),
            policy_version=self.policy.get("version", "unknown"),
            readiness=(
                "gold_eval_pack_ready"
                if production_ready
                else "gold_eval_pack_blocked_until_attorney_reviewed_jsonl_meets_minimums"
            ),
        )

    def _audit_dataset(
        self,
        dataset: str,
        minimum_rows: int,
        findings: list[GoldDatasetFinding],
        blockers: list[str],
    ) -> GoldDatasetStatus:
        path = self.eval_root / dataset
        rows = 0
        attorney_reviewed_rows = 0
        synthetic_or_seed_rows = 0
        private_training_rows = 0
        rows_missing_required_fields = 0
        parse_errors = 0
        required_fields = list(self.policy.get("required_fields", []))

        if not path.exists():
            blockers.append(f"gold_dataset_missing:{dataset}")
            findings.append(
                GoldDatasetFinding(
                    dataset=dataset,
                    row_number=None,
                    code="gold_dataset_missing",
                    message=f"Dataset not found: {path}",
                )
            )
            return GoldDatasetStatus(
                dataset=dataset,
                rows=0,
                minimum_rows=minimum_rows,
                attorney_reviewed_rows=0,
                synthetic_or_seed_rows=0,
                private_training_rows=0,
                rows_missing_required_fields=0,
                parse_errors=0,
                status="blocked_missing_dataset",
            )

        with path.open("r", encoding="utf-8") as handle:
            for row_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    parse_errors += 1
                    findings.append(
                        GoldDatasetFinding(
                            dataset=dataset,
                            row_number=row_number,
                            code="json_parse_error",
                            message=str(exc),
                        )
                    )
                    continue
                rows += 1
                missing = [field for field in required_fields if field not in row]
                if missing:
                    rows_missing_required_fields += 1
                    findings.append(
                        GoldDatasetFinding(
                            dataset=dataset,
                            row_number=row_number,
                            code="missing_required_fields",
                            message=", ".join(missing),
                        )
                    )
                review_status = str(row.get("review_status", "")).lower()
                method = str(row.get("annotator_or_generation_method", "")).lower()
                if "attorney" in review_status and "not_attorney" not in review_status:
                    attorney_reviewed_rows += 1
                if "seed" in review_status or "seed" in method or "synthetic" in method:
                    synthetic_or_seed_rows += 1
                if row.get("private_data_allowed_for_training") is True:
                    private_training_rows += 1

        status = "pass"
        if rows < minimum_rows:
            status = "blocked_minimum_rows"
            blockers.append(f"gold_rows_minimum_not_met:{dataset}")
        elif self.policy.get("attorney_review_required", True) and attorney_reviewed_rows < minimum_rows:
            status = "blocked_attorney_review_rows"
            blockers.append(f"attorney_gold_rows_minimum_not_met:{dataset}")
        if rows_missing_required_fields:
            status = "blocked_missing_required_fields"
            blockers.append(f"gold_dataset_missing_required_fields:{dataset}")
        if parse_errors:
            status = "blocked_parse_errors"
            blockers.append(f"gold_dataset_parse_errors:{dataset}")
        if private_training_rows and not self.policy.get("private_data_training_allowed", False):
            status = "blocked_private_training_rows"
            blockers.append(f"private_training_rows_in_gold_dataset:{dataset}")

        return GoldDatasetStatus(
            dataset=dataset,
            rows=rows,
            minimum_rows=minimum_rows,
            attorney_reviewed_rows=attorney_reviewed_rows,
            synthetic_or_seed_rows=synthetic_or_seed_rows,
            private_training_rows=private_training_rows,
            rows_missing_required_fields=rows_missing_required_fields,
            parse_errors=parse_errors,
            status=status,
        )


class GoldAnnotationQueueBuilder:
    """Create an attorney annotation queue from an authority manifest.

    The queue is not a gold dataset. It is a controlled worklist that lets
    reviewers create gold rows without mixing private matter data into the source
    repository or pretending generated rows have been lawyer-approved.
    """

    def __init__(self, *, policy: dict[str, Any] | None = None, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.policy = policy or json.loads(
            (self.project_root / "configs" / "maine_gold_eval_pack_policy.json").read_text(
                encoding="utf-8"
            )
        )

    def build_from_manifest(
        self,
        *,
        manifest_path: str | Path,
        output_path: str | Path,
        max_items_per_task_type: int = 25,
        reviewer_ids: list[str] | None = None,
        double_review: bool = True,
        csv_output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if not isinstance(manifest, list):
            raise ValueError("source manifest must be a JSON array")
        source_records = [item for item in manifest if isinstance(item, dict)]
        task_types = list(self.policy.get("annotation_queue_task_types", []))
        reviewers = [item for item in (reviewer_ids or []) if item]
        rows: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()
        for task_type in task_types:
            for item_index, record in enumerate(source_records[:max_items_per_task_type]):
                source_id = str(record.get("source_id", ""))
                source_class = str(record.get("source_class", ""))
                text_seed = f"{task_type}|{source_id}|{record.get('hash', '')}"
                primary, secondary = _reviewer_pair(reviewers, len(rows), double_review)
                row = {
                    "queue_id": _stable_queue_id(text_seed),
                    "task_type": task_type,
                    "source_id": source_id,
                    "source_class": source_class,
                    "jurisdiction": record.get("jurisdiction", "maine"),
                    "source_url_or_path": record.get("source_url_or_path"),
                    "snapshot_path": record.get("snapshot_path"),
                    "snapshot_hash": record.get("hash"),
                    "parser_status": record.get("parser_status"),
                    "freshness_status": record.get("freshness_status"),
                    "review_status": "needs_attorney_review",
                    "review_workflow_status": "queued",
                    "primary_reviewer_id": primary,
                    "secondary_reviewer_id": secondary,
                    "double_review_required": bool(double_review),
                    "conflict_status": "not_started",
                    "conflict_resolver_id": None,
                    "promoted_gold_dataset": _dataset_for_task_type(task_type),
                    "private_data_allowed_for_training": False,
                    "created_at": now,
                    "assignment_batch": _stable_queue_id(f"batch|{task_type}|{item_index}|{now}"),
                    "instructions": _task_instructions(task_type),
                }
                rows.append(row)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        csv_output = None
        if csv_output_path:
            csv_output = Path(csv_output_path)
            export_annotation_queue_csv(rows, csv_output)
        return {
            "status": "pass",
            "manifest_path": str(manifest_path),
            "output_path": str(output),
            "csv_output_path": str(csv_output) if csv_output else None,
            "source_records": len(source_records),
            "task_types": task_types,
            "queue_rows": len(rows),
            "review_status": "needs_attorney_review",
            "double_review_required": bool(double_review),
            "assigned_rows": sum(1 for row in rows if row.get("primary_reviewer_id")),
            "conflict_resolution_status": "not_started",
        }


@dataclass(frozen=True)
class AnnotationQueueAuditReport:
    queue_path: str
    rows: int
    assigned_rows: int
    double_review_rows: int
    needs_attorney_review_rows: int
    private_training_rows: int
    parse_errors: int
    missing_required_fields: int
    task_type_counts: dict[str, int]
    status: str
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queue_path": self.queue_path,
            "rows": self.rows,
            "assigned_rows": self.assigned_rows,
            "double_review_rows": self.double_review_rows,
            "needs_attorney_review_rows": self.needs_attorney_review_rows,
            "private_training_rows": self.private_training_rows,
            "parse_errors": self.parse_errors,
            "missing_required_fields": self.missing_required_fields,
            "task_type_counts": self.task_type_counts,
            "status": self.status,
            "blockers": sorted(set(self.blockers)),
        }


class GoldAnnotationQueueAuditor:
    """Audit annotation queues without treating them as gold data."""

    REQUIRED_QUEUE_FIELDS = {
        "queue_id",
        "task_type",
        "source_id",
        "source_class",
        "jurisdiction",
        "review_status",
        "double_review_required",
        "conflict_status",
        "promoted_gold_dataset",
        "private_data_allowed_for_training",
        "created_at",
        "instructions",
    }

    def audit(self, queue_path: str | Path) -> AnnotationQueueAuditReport:
        path = Path(queue_path)
        blockers: list[str] = []
        rows = 0
        assigned_rows = 0
        double_review_rows = 0
        needs_attorney_review_rows = 0
        private_training_rows = 0
        parse_errors = 0
        missing_required_fields = 0
        task_type_counts: dict[str, int] = {}
        if not path.exists():
            return AnnotationQueueAuditReport(
                queue_path=str(path),
                rows=0,
                assigned_rows=0,
                double_review_rows=0,
                needs_attorney_review_rows=0,
                private_training_rows=0,
                parse_errors=0,
                missing_required_fields=0,
                task_type_counts={},
                status="blocked_missing_queue",
                blockers=["annotation_queue_missing"],
            )
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
                task_type = str(row.get("task_type", "unknown"))
                task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
                if self.REQUIRED_QUEUE_FIELDS - set(row):
                    missing_required_fields += 1
                if row.get("review_status") == "needs_attorney_review":
                    needs_attorney_review_rows += 1
                if row.get("primary_reviewer_id"):
                    assigned_rows += 1
                if row.get("double_review_required") is True:
                    double_review_rows += 1
                if row.get("private_data_allowed_for_training") is True:
                    private_training_rows += 1
        if rows == 0:
            blockers.append("annotation_queue_empty")
        if parse_errors:
            blockers.append("annotation_queue_parse_errors")
        if missing_required_fields:
            blockers.append("annotation_queue_missing_required_fields")
        if private_training_rows:
            blockers.append("annotation_queue_private_training_not_allowed")
        if needs_attorney_review_rows != rows:
            blockers.append("annotation_queue_rows_must_remain_needs_attorney_review")
        return AnnotationQueueAuditReport(
            queue_path=str(path),
            rows=rows,
            assigned_rows=assigned_rows,
            double_review_rows=double_review_rows,
            needs_attorney_review_rows=needs_attorney_review_rows,
            private_training_rows=private_training_rows,
            parse_errors=parse_errors,
            missing_required_fields=missing_required_fields,
            task_type_counts=dict(sorted(task_type_counts.items())),
            status="pass" if not blockers else "blocked",
            blockers=blockers,
        )


class GoldEvalPackManifestBuilder:
    """Create a manifest of required gold datasets and current audited row counts."""

    def __init__(self, *, project_root: str | Path = ".", policy: dict[str, Any] | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.policy = policy or json.loads(
            (self.project_root / "configs" / "maine_gold_eval_pack_policy.json").read_text(
                encoding="utf-8"
            )
        )

    def build(self, *, eval_root: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
        report = GoldEvalPackAuditor(
            project_root=self.project_root,
            eval_root=eval_root,
            policy=self.policy,
        ).run()
        manifest = {
            "status": "pass",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "eval_root": str(Path(eval_root).resolve()),
            "policy_version": self.policy.get("version", "unknown"),
            "attorney_review_required": self.policy.get("attorney_review_required", True),
            "private_data_training_allowed": self.policy.get("private_data_training_allowed", False),
            "production_ready": report.production_ready,
            "readiness": report.readiness,
            "datasets": [status.as_dict() for status in report.datasets],
            "blockers": report.as_dict()["blockers"],
        }
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest



@dataclass(frozen=True)
class GoldPromotionReport:
    input_path: str
    eval_root: str
    output_report_path: str | None
    status: str
    eligible_rows: int
    skipped_rows: int
    written_rows: int
    dataset_counts: dict[str, int]
    blockers: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path,
            "eval_root": self.eval_root,
            "output_report_path": self.output_report_path,
            "status": self.status,
            "eligible_rows": self.eligible_rows,
            "skipped_rows": self.skipped_rows,
            "written_rows": self.written_rows,
            "dataset_counts": dict(sorted(self.dataset_counts.items())),
            "blockers": sorted(set(self.blockers)),
            "findings": self.findings,
        }


class ReviewedGoldAnnotationPromoter:
    """Promote attorney-reviewed annotation queue rows into gold JSONL datasets.

    This is deliberately fail-closed: queued rows are not gold; only rows marked as
    attorney-reviewed and containing the required gold fields can be promoted. The
    promoter never writes private-training rows and never fabricates labels or spans.
    """

    ATTORNEY_REVIEW_STATUSES = {
        "attorney_reviewed",
        "attorney_reviewed_final",
        "attorney_reviewed_approved",
        "attorney_approved",
    }

    def __init__(self, *, project_root: str | Path = ".", policy: dict[str, Any] | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.policy = policy or json.loads(
            (self.project_root / "configs" / "maine_gold_eval_pack_policy.json").read_text(
                encoding="utf-8"
            )
        )
        self.required_fields = list(self.policy.get("required_fields", []))

    def promote(
        self,
        *,
        reviewed_queue_path: str | Path,
        eval_root: str | Path,
        output_report_path: str | Path | None = None,
        append: bool = False,
    ) -> GoldPromotionReport:
        input_path = Path(reviewed_queue_path)
        root = Path(eval_root)
        findings: list[dict[str, Any]] = []
        blockers: list[str] = []
        dataset_rows: dict[str, list[dict[str, Any]]] = {}
        skipped_rows = 0
        eligible_rows = 0

        if not input_path.exists():
            blockers.append("reviewed_annotation_queue_missing")
            return self._finish(
                input_path=input_path,
                eval_root=root,
                output_report_path=output_report_path,
                status="blocked",
                eligible_rows=0,
                skipped_rows=0,
                written_rows=0,
                dataset_counts={},
                blockers=blockers,
                findings=findings,
            )

        with input_path.open("r", encoding="utf-8") as handle:
            for row_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "json_parse_error",
                            "message": str(exc),
                        }
                    )
                    continue

                review_status = str(row.get("review_status", "")).lower()
                if review_status not in self.ATTORNEY_REVIEW_STATUSES:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "not_attorney_reviewed",
                            "message": f"review_status={review_status or '<missing>'}",
                        }
                    )
                    continue

                if row.get("private_data_allowed_for_training") is True:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "private_training_not_allowed",
                            "message": "private_data_allowed_for_training must be false",
                        }
                    )
                    continue

                missing = [field for field in self.required_fields if field not in row]
                if missing:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "missing_required_gold_fields",
                            "message": ", ".join(missing),
                        }
                    )
                    continue

                method = str(row.get("annotator_or_generation_method", "")).lower()
                if "attorney" not in method or "seed" in method or "synthetic" in method:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "invalid_annotator_method",
                            "message": "annotator_or_generation_method must be attorney_review and not seed/synthetic",
                        }
                    )
                    continue

                dataset = str(row.get("promoted_gold_dataset") or _dataset_for_task_type(str(row.get("task_type", ""))))
                if not dataset.endswith(".jsonl") or "/" in dataset or "\\" in dataset:
                    skipped_rows += 1
                    findings.append(
                        {
                            "row_number": row_number,
                            "code": "invalid_promoted_gold_dataset",
                            "message": dataset,
                        }
                    )
                    continue

                gold_row = {field: row.get(field) for field in self.required_fields}
                for optional_field in (
                    "task_type",
                    "queue_id",
                    "source_url_or_path",
                    "snapshot_hash",
                    "reviewer_id",
                    "primary_reviewer_id",
                    "secondary_reviewer_id",
                    "conflict_status",
                    "conflict_resolver_id",
                ):
                    if optional_field in row:
                        gold_row[optional_field] = row.get(optional_field)
                dataset_rows.setdefault(dataset, []).append(gold_row)
                eligible_rows += 1

        if eligible_rows == 0:
            blockers.append("no_attorney_reviewed_gold_rows_to_promote")

        written_rows = 0
        if not blockers:
            root.mkdir(parents=True, exist_ok=True)
            for dataset, rows in sorted(dataset_rows.items()):
                target = root / dataset
                mode = "a" if append and target.exists() else "w"
                with target.open(mode, encoding="utf-8") as handle:
                    for row in rows:
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
                        written_rows += 1

        return self._finish(
            input_path=input_path,
            eval_root=root,
            output_report_path=output_report_path,
            status="pass" if not blockers else "blocked",
            eligible_rows=eligible_rows,
            skipped_rows=skipped_rows,
            written_rows=written_rows,
            dataset_counts={dataset: len(rows) for dataset, rows in dataset_rows.items()},
            blockers=blockers,
            findings=findings,
        )

    def _finish(
        self,
        *,
        input_path: Path,
        eval_root: Path,
        output_report_path: str | Path | None,
        status: str,
        eligible_rows: int,
        skipped_rows: int,
        written_rows: int,
        dataset_counts: dict[str, int],
        blockers: list[str],
        findings: list[dict[str, Any]],
    ) -> GoldPromotionReport:
        report_path = Path(output_report_path) if output_report_path else None
        report = GoldPromotionReport(
            input_path=str(input_path),
            eval_root=str(eval_root),
            output_report_path=str(report_path) if report_path else None,
            status=status,
            eligible_rows=eligible_rows,
            skipped_rows=skipped_rows,
            written_rows=written_rows,
            dataset_counts=dataset_counts,
            blockers=blockers,
            findings=findings,
        )
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

def export_annotation_queue_csv(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "queue_id",
        "task_type",
        "source_id",
        "source_class",
        "jurisdiction",
        "review_status",
        "primary_reviewer_id",
        "secondary_reviewer_id",
        "double_review_required",
        "conflict_status",
        "promoted_gold_dataset",
        "private_data_allowed_for_training",
        "instructions",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _stable_queue_id(seed: str) -> str:
    return "queue_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _reviewer_pair(reviewers: list[str], index: int, double_review: bool) -> tuple[str | None, str | None]:
    if not reviewers:
        return None, None
    primary = reviewers[index % len(reviewers)]
    if not double_review or len(reviewers) == 1:
        return primary, None
    secondary = reviewers[(index + 1) % len(reviewers)]
    return primary, secondary if secondary != primary else None


def _dataset_for_task_type(task_type: str) -> str:
    return {
        "rag_retrieval": "maine_rag_retrieval_gold.jsonl",
        "citation_validity": "maine_citation_validity_gold.jsonl",
        "quote_span": "maine_quote_span_gold.jsonl",
        "hallucination_negative": "maine_hallucination_negative_cases.jsonl",
        "forms_freshness": "maine_forms_freshness_gold.jsonl",
        "drafting_review": "maine_drafting_review_gold.jsonl",
        "issue_classification": "maine_issue_classification_gold.jsonl",
        "posture_classification": "maine_posture_classification_gold.jsonl",
        "authority_ranking": "maine_authority_ranking_gold.jsonl",
        "fact_to_evidence": "maine_fact_to_evidence_gold.jsonl",
        "law_court_holding": "maine_law_court_holding_gold.jsonl",
        "rule_52_gap": "maine_rule_52_gap_gold.jsonl",
    }.get(task_type, f"{task_type}_gold.jsonl")


def _task_instructions(task_type: str) -> str:
    instructions = {
        "rag_retrieval": "Write a realistic Maine family-law query and identify the expected source IDs.",
        "citation_validity": "Create or verify a citation and mark whether it resolves to this source.",
        "quote_span": "Select an exact quote span and record offsets or normalized quote text.",
        "hallucination_negative": "Create a false-premise prompt that this source proves should be rejected.",
        "forms_freshness": "Check whether the form/source version is current and note freshness evidence.",
        "drafting_review": "Create a draft-review issue requiring citations, facts, or human review.",
        "issue_classification": "Label the Maine family-law issues represented by this source text.",
        "posture_classification": "Label procedural posture signals represented by this source text.",
        "authority_ranking": "Compare this authority against another class and rank controlling authority.",
        "fact_to_evidence": "Map a sample fact to a quote or source span from this authority.",
        "law_court_holding": "Extract holding, disposition, posture, and review standard if this is an opinion.",
        "rule_52_gap": "Create or identify a findings-gap example relevant to Rule 52/family orders.",
    }
    return instructions.get(task_type, "Create an attorney-reviewed gold-eval row from this source.")
