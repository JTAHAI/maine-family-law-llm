from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.external_eval_root import ExternalEvalRootLayout, external_eval_root_layout
from legal.evals.gold_pack import (
    GoldAnnotationQueueBuilder,
    GoldEvalPackAuditor,
)
from legal.evals.release_metrics import ReleaseMetricsEvidenceBuilder

DATASET_NAMES = (
    "maine_rag_retrieval_gold.jsonl",
    "maine_citation_validity_gold.jsonl",
    "maine_quote_span_gold.jsonl",
    "maine_hallucination_negative_cases.jsonl",
    "maine_forms_freshness_gold.jsonl",
    "maine_drafting_review_gold.jsonl",
    "maine_issue_classification_gold.jsonl",
    "maine_posture_classification_gold.jsonl",
    "maine_authority_ranking_gold.jsonl",
    "maine_fact_to_evidence_gold.jsonl",
    "maine_law_court_holding_gold.jsonl",
    "maine_rule_52_gap_gold.jsonl",
)

COMMON_SCHEMA_REQUIRED_FIELDS = [
    "row_id",
    "dataset_type",
    "schema_version",
    "source_id",
    "source_class",
    "jurisdiction",
    "authority_build_id",
    "source_hash",
    "source_span",
    "question",
    "expected_result",
    "accepted_labels",
    "rejected_labels",
    "issue_tags",
    "posture_tags",
    "reviewer_safe_id",
    "second_reviewer_safe_id",
    "adjudicator_safe_id",
    "reviewer_role",
    "review_created_at",
    "second_review_created_at",
    "adjudication_status",
    "confidence",
    "rationale_summary",
    "private_data_allowed_for_training",
    "synthetic",
    "seed",
    "attorney_reviewed",
    "promoted_to_gold",
    "row_hash",
    "supersedes_row_id",
    "notes",
    "audit_chain_reference",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_row_view(row: dict[str, Any]) -> dict[str, Any]:
    blocked = {"source_url_or_path", "snapshot_path", "reviewer_secret", "absolute_path"}
    return {key: value for key, value in row.items() if key not in blocked}


@dataclass(frozen=True)
class ReviewLabPaths:
    layout: ExternalEvalRootLayout

    @property
    def queue_path(self) -> Path:
        return self.layout.annotation_queue / "gold_annotation_queue.jsonl"

    @property
    def queue_summary_path(self) -> Path:
        return self.layout.annotation_queue / "gold_annotation_queue_summary.json"

    @property
    def reviews_path(self) -> Path:
        return self.layout.reviews / "reviews.jsonl"

    @property
    def adjudications_path(self) -> Path:
        return self.layout.adjudications / "adjudications.jsonl"

    @property
    def assignments_path(self) -> Path:
        return self.layout.assignments / "assignments.jsonl"

    @property
    def recusals_path(self) -> Path:
        return self.layout.reviews / "recusals.jsonl"

    @property
    def corrections_path(self) -> Path:
        return self.layout.promoted_gold / "corrections.jsonl"

    @property
    def runs_ledger_path(self) -> Path:
        return self.layout.runs / "runs.jsonl"

    def dataset_path(self, dataset_id: str) -> Path:
        return self.layout.datasets / dataset_id

    def promoted_dataset_path(self, dataset_id: str) -> Path:
        return self.layout.promoted_gold / dataset_id

    def run_path(self, run_id: str) -> Path:
        return self.layout.runs / f"{run_id}.json"

    def metrics_path(self, run_id: str) -> Path:
        return self.layout.metrics / f"{run_id}.json"

    def failure_cluster_path(self, run_id: str) -> Path:
        return self.layout.failure_clusters / f"{run_id}.json"

    def release_comparison_path(self, run_id: str) -> Path:
        return self.layout.release_comparisons / f"{run_id}.json"


class EvalReviewStudioError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EvalReviewStudio:
    """Append-only external review workflow for attorney-reviewed eval data."""

    BLIND_REVIEW_STATUSES = {"pending", "blind_pending", "second_review_pending"}
    REVIEWER_ROLES = {"attorney_reviewer", "supervised_attorney_reviewer", "adjudicator", "reviewer"}

    def __init__(self, project_root: str | Path = ".", eval_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = external_eval_root_layout(eval_root, project_root=self.project_root, create=True)
        self.paths = ReviewLabPaths(self.layout)
        self.layout.ensure()
        self._ensure_dataset_schemas()

    def status(self) -> dict[str, Any]:
        queue = _load_jsonl(self.paths.queue_path)
        reviews = self._review_events()
        recusals = self._recusal_events()
        adjudications = _load_jsonl(self.paths.adjudications_path)
        promotions = _load_jsonl(self.layout.promoted_gold / "promotions.jsonl")
        audit = GoldEvalPackAuditor(project_root=self.project_root, eval_root=self.layout.root).run()
        reviewed_rows = sum(1 for row in queue if str(row.get("review_status")) not in {"needs_attorney_review", "queued"})
        conflicts = sum(1 for row in adjudications if str(row.get("adjudication_status")) == "conflict_resolved")
        stale_rows = sum(1 for row in queue if str(row.get("freshness_status", "")).casefold() not in {"current", "fresh", "known_extracted_timestamp"})
        honest_participation = self._honest_participation_report(
            reviews=reviews,
            recusals=recusals,
            adjudications=adjudications,
            promotions=promotions,
        )
        unreviewed_rows = max(0, len(queue) - reviewed_rows)
        return {
            "status": "pass",
            "readiness": audit.readiness,
            "eval_root": str(self.layout.root),
            "dataset_count": len(audit.datasets),
            "dataset_rows": {item.dataset: item.rows for item in audit.datasets},
            "dataset_manifest": self.dataset_manifest(),
            "reviewed_rows": reviewed_rows,
            "unreviewed_rows": unreviewed_rows,
            "conflicts": conflicts,
            "promoted_gold_rows": len(promotions),
            "stale_rows": stale_rows,
            "attorney_review_events": honest_participation["attorney_review_events"],
            "blind_reviews": sum(1 for row in reviews if bool(row.get("blind"))),
            "disagreements": sum(1 for row in reviews if bool(row.get("disagreement_detected"))),
            "recusals": len(recusals),
            "superseded_rows": len(_load_jsonl(self.paths.corrections_path)),
            "honest_participation": honest_participation,
            "eligibility": self._eligibility_report(audit=audit, honest_participation=honest_participation),
            "release_blockers": list(audit.blockers),
            "review_ledger_rows": len(reviews),
        }

    def _ensure_dataset_schemas(self) -> None:
        schema_manifest = {"schema_version": "attorney_review_studio_schema_manifest_v1", "datasets": []}
        for dataset_id in DATASET_NAMES:
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "schema_version": "attorney_review_studio_dataset_schema_v1",
                "dataset_id": dataset_id,
                "type": "object",
                "required": COMMON_SCHEMA_REQUIRED_FIELDS,
                "properties": {field: {"type": ["string", "number", "boolean", "array", "object", "null"]} for field in COMMON_SCHEMA_REQUIRED_FIELDS},
                "additionalProperties": True,
            }
            schema_path = self.layout.schemas / f"{dataset_id}.schema.json"
            if not schema_path.exists():
                _write_json(schema_path, schema)
            schema_manifest["datasets"].append({"dataset_id": dataset_id, "schema_path": schema_path.name})
        manifest_path = self.layout.schemas / "schema_manifest.json"
        if not manifest_path.exists():
            _write_json(manifest_path, schema_manifest)

    def build_queue(
        self,
        *,
        manifest_path: str | Path,
        output_path: str | Path | None = None,
        max_items_per_task_type: int = 25,
        reviewer_ids: list[str] | None = None,
        double_review: bool = True,
        csv_output_path: str | Path | None = None,
        dataset_filter: list[str] | None = None,
        source_class_filter: list[str] | None = None,
        issue_filter: list[str] | None = None,
        posture_filter: list[str] | None = None,
        target_dataset_type: str | None = None,
        seed: int | str | None = None,
        dry_run: bool = False,
        include_fixture_candidates: bool = False,
    ) -> dict[str, Any]:
        builder = GoldAnnotationQueueBuilder(project_root=self.project_root)
        summary = builder.build_from_manifest(
            manifest_path=manifest_path,
            output_path=output_path or self.paths.queue_path,
            max_items_per_task_type=max_items_per_task_type,
            reviewer_ids=reviewer_ids,
            double_review=double_review,
            csv_output_path=csv_output_path,
            dataset_filter=dataset_filter,
            source_class_filter=source_class_filter,
            issue_filter=issue_filter,
            posture_filter=posture_filter,
            target_dataset_type=target_dataset_type,
            seed=seed,
            dry_run=dry_run,
            include_fixture_candidates=include_fixture_candidates,
            summary_output_path=self.paths.queue_summary_path,
        )
        if not dry_run and output_path is None and Path(summary["output_path"]).exists():
            _append_jsonl(self.paths.assignments_path, {"event": "queue_built", "generated_at": _now(), **summary})
        return summary

    def list_assignments(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        rows = _load_jsonl(self.paths.queue_path)
        sliced = rows[offset : offset + max(1, min(limit, 500))]
        return {
            "status": "pass",
            "total_rows": len(rows),
            "offset": offset,
            "limit": limit,
            "rows": [_safe_row_view(row) for row in sliced],
        }

    def record_recusal(
        self,
        row_id: str,
        *,
        reviewer_safe_id: str,
        reviewer_role: str,
        reason: str,
        conflict_of_interest_note: str = "",
        comments: str = "",
    ) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        if reviewer_role not in self.REVIEWER_ROLES:
            raise EvalReviewStudioError("reviewer_role_required", "A reviewer role is required.", status_code=403)
        event = {
            "event_type": "recusal",
            "row_id": row_id,
            "dataset_type": row.get("dataset_type") or row.get("promoted_gold_dataset"),
            "reviewer_safe_id": reviewer_safe_id,
            "reviewer_role": reviewer_role,
            "reason": reason[:1000],
            "conflict_of_interest_note": conflict_of_interest_note[:1000],
            "comments": comments[:1000],
            "recused_at": _now(),
            "review_workflow_status": "recused",
        }
        _append_jsonl(self.paths.recusals_path, event)
        _append_jsonl(self.paths.assignments_path, {"event": "recusal_recorded", "generated_at": _now(), **event})
        return {"status": "pass", "row": self._row_payload(row), "recusal": event}

    def get_row(self, row_id: str) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        return self._row_payload(row)

    def review_row(
        self,
        row_id: str,
        *,
        reviewer_safe_id: str,
        reviewer_role: str,
        decision: str,
        confidence: float,
        rationale: str,
        blind: bool = False,
        conflict_of_interest_note: str = "",
        comments: str = "",
    ) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        if reviewer_role not in self.REVIEWER_ROLES:
            raise EvalReviewStudioError("reviewer_role_required", "A reviewer role is required.", status_code=403)
        prior_reviews = self._reviews_for(row_id)
        if blind and prior_reviews:
            visible_prior = []
        else:
            visible_prior = prior_reviews
        event = {
            "event_type": "first_review" if not prior_reviews else "second_review",
            "row_id": row_id,
            "dataset_type": row.get("dataset_type") or row.get("promoted_gold_dataset"),
            "reviewer_safe_id": reviewer_safe_id,
            "reviewer_role": reviewer_role,
            "decision": decision,
            "confidence": float(confidence),
            "rationale_summary": rationale[:1000],
            "blind": bool(blind),
            "conflict_of_interest_note": conflict_of_interest_note[:500],
            "comments": comments[:1000],
            "reviewed_at": _now(),
            "reviewer_status": "attorney_reviewed" if "attorney" in reviewer_role else reviewer_role,
            "prior_reviews_visible_to_reviewer": [self._public_review_view(item) for item in visible_prior],
        }
        if bool(row.get("seed")) or bool(row.get("synthetic")):
            event["review_status"] = "seed_or_synthetic"
        if str(row.get("freshness_status", "")).casefold() in {"stale", "unknown", "superseded", "retrieval_failed", "parser_failed"}:
            event["freshness_status"] = row.get("freshness_status")
        _append_jsonl(self.paths.reviews_path, event)
        return {
            "status": "pass",
            "row": self._row_payload(row),
            "review": event,
            "disagreement_detected": self._has_disagreement(row_id, decision),
        }

    def second_review_row(self, row_id: str, **payload: Any) -> dict[str, Any]:
        payload.setdefault("blind", True)
        return self.review_row(row_id, **payload)

    def adjudicate_row(
        self,
        row_id: str,
        *,
        adjudicator_safe_id: str,
        adjudication_status: str,
        resolution_label: str,
        rationale: str,
        fixed_in_version: str = "",
        supersedes_row_id: str | None = None,
        release_blocker: bool = False,
        owner_status: str = "",
    ) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        record = {
            "event_type": "adjudication",
            "row_id": row_id,
            "dataset_type": row.get("dataset_type") or row.get("promoted_gold_dataset"),
            "adjudicator_safe_id": adjudicator_safe_id,
            "adjudication_status": adjudication_status,
            "resolution_label": resolution_label,
            "rationale_summary": rationale[:1500],
            "fixed_in_version": fixed_in_version,
            "supersedes_row_id": supersedes_row_id,
            "release_blocker": bool(release_blocker),
            "owner_status": owner_status,
            "adjudicated_at": _now(),
            "history": {
                "reviews": [_safe_row_view(item) for item in self._reviews_for(row_id)],
            },
        }
        _append_jsonl(self.paths.adjudications_path, record)
        if adjudication_status in {"resolved", "accepted", "promote"}:
            promoted = self.promote_row(
                row_id,
                adjudicator_safe_id=adjudicator_safe_id,
                supersedes_row_id=supersedes_row_id,
                notes=rationale,
            )
            record["promotion_result"] = promoted
        return {"status": "pass", "row": self._row_payload(row), "adjudication": record}

    def supersede_row(
        self,
        row_id: str,
        *,
        adjudicator_safe_id: str,
        rationale: str,
        corrected_labels: list[str] | None = None,
        fixed_in_version: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        reviews = self._reviews_for(row_id)
        latest_review = reviews[-1] if reviews else {}
        latest_adjudication = next(
            (
                item
                for item in reversed(_load_jsonl(self.paths.adjudications_path))
                if str(item.get("row_id")) == str(row_id)
            ),
            {},
        )
        correction_row_id = f"{row_id}_supersede_{uuid.uuid4().hex[:10]}"
        promoted = {
            **_safe_row_view(row),
            "row_id": correction_row_id,
            "queue_id": correction_row_id,
            "attorney_reviewed": True,
            "promoted_to_gold": True,
            "adjudicator_safe_id": adjudicator_safe_id,
            "reviewer_role": latest_review.get("reviewer_role"),
            "reviewer_safe_id": latest_review.get("reviewer_safe_id", row.get("reviewer_safe_id")),
            "second_reviewer_safe_id": row.get("second_reviewer_safe_id"),
            "review_created_at": reviews[0].get("reviewed_at") if reviews else None,
            "second_review_created_at": reviews[1].get("reviewed_at") if len(reviews) > 1 else None,
            "review_status": "attorney_reviewed_final",
            "independent_review_status": "completed" if row.get("double_review_required") else "single_review_completed",
            "adjudication_status": latest_adjudication.get("adjudication_status", "resolved"),
            "decision_history": [self._public_review_view(item) for item in reviews],
            "conflict_resolution_status": latest_adjudication.get("adjudication_status", "resolved"),
            "supersedes_row_id": row_id,
            "fixed_in_version": fixed_in_version,
            "correction_status": "superseding_correction",
            "corrected_labels": corrected_labels or [],
            "notes": notes[:1500] if notes else rationale[:1500],
            "promoted_at": _now(),
            "row_hash": _sha({"row_id": row_id, "corrected_labels": corrected_labels or [], "rationale": rationale}),
            "text_span": row.get("source_span") or row.get("text_span") or row.get("span"),
            "label": corrected_labels or row.get("accepted_labels") or ([row.get("expected_result")] if row.get("expected_result") else []),
            "annotator_or_generation_method": "attorney_review",
            "confidence": float(latest_review.get("confidence") or row.get("confidence") or 1.0),
            "hash": row.get("source_hash") or row.get("hash") or row.get("row_hash"),
            "created_at": row.get("created_at") or _now(),
            "private_data_allowed_for_training": False,
        }
        dataset_id = str(row.get("promoted_gold_dataset") or row.get("dataset_type") or "maine_rag_retrieval_gold.jsonl")
        dataset_path = self.paths.dataset_path(dataset_id)
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        _append_jsonl(dataset_path, promoted)
        promoted_ledger = self.layout.promoted_gold / "promotions.jsonl"
        _append_jsonl(
            promoted_ledger,
            {
                "row_id": correction_row_id,
                "source_row_id": row_id,
                "dataset_id": dataset_id,
                "promoted_at": promoted["promoted_at"],
                "promoted_to_gold": True,
                "supersedes_row_id": row_id,
                "correction_status": "superseding_correction",
            },
        )
        supersession = {
            "event_type": "supersession",
            "row_id": row_id,
            "supersedes_row_id": row_id,
            "superseded_by_row_id": correction_row_id,
            "adjudicator_safe_id": adjudicator_safe_id,
            "fixed_in_version": fixed_in_version,
            "corrected_labels": corrected_labels or [],
            "rationale_summary": rationale[:1500],
            "superseded_at": _now(),
            "notes": notes[:1500] if notes else rationale[:1500],
        }
        _append_jsonl(self.paths.corrections_path, supersession)
        return {"status": "pass", "row": self._row_payload(row), "promoted_row": promoted, "supersession": supersession}

    def promote_row(
        self,
        row_id: str,
        *,
        adjudicator_safe_id: str,
        supersedes_row_id: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        row = self._find_row(row_id)
        if not row:
            raise EvalReviewStudioError("eval_row_not_found", f"Row not found: {row_id}", status_code=404)
        reviews = self._reviews_for(row_id)
        latest_review = reviews[-1] if reviews else {}
        latest_adjudication = next(
            (
                item
                for item in reversed(_load_jsonl(self.paths.adjudications_path))
                if str(item.get("row_id")) == str(row_id)
            ),
            {},
        )
        promoted_row = {
            **_safe_row_view(row),
            "attorney_reviewed": True,
            "promoted_to_gold": True,
            "adjudicator_safe_id": adjudicator_safe_id,
            "reviewer_role": latest_review.get("reviewer_role"),
            "reviewer_safe_id": latest_review.get("reviewer_safe_id", row.get("reviewer_safe_id")),
            "second_reviewer_safe_id": row.get("second_reviewer_safe_id"),
            "review_created_at": reviews[0].get("reviewed_at") if reviews else None,
            "second_review_created_at": reviews[1].get("reviewed_at") if len(reviews) > 1 else None,
            "review_status": "attorney_reviewed_final",
            "independent_review_status": "completed" if row.get("double_review_required") else "single_review_completed",
            "adjudication_status": latest_adjudication.get("adjudication_status", "resolved"),
            "decision_history": [self._public_review_view(item) for item in reviews],
            "conflict_resolution_status": latest_adjudication.get("adjudication_status", "resolved"),
            "supersedes_row_id": supersedes_row_id,
            "notes": notes[:1500] if notes else row.get("notes", ""),
            "promoted_at": _now(),
            "row_hash": _sha(row),
            "text_span": row.get("source_span") or row.get("text_span") or row.get("span"),
            "label": row.get("accepted_labels") or ([row.get("expected_result")] if row.get("expected_result") else []),
            "annotator_or_generation_method": "attorney_review",
            "confidence": float(latest_review.get("confidence") or row.get("confidence") or 1.0),
            "hash": row.get("source_hash") or row.get("hash") or row.get("row_hash"),
            "created_at": row.get("created_at") or _now(),
            "private_data_allowed_for_training": False,
        }
        dataset_id = str(row.get("promoted_gold_dataset") or row.get("dataset_type") or "maine_rag_retrieval_gold.jsonl")
        dataset_path = self.paths.dataset_path(dataset_id)
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        _append_jsonl(dataset_path, promoted_row)
        promoted_ledger = self.layout.promoted_gold / "promotions.jsonl"
        _append_jsonl(promoted_ledger, {"row_id": row_id, "dataset_id": dataset_id, "promoted_at": promoted_row["promoted_at"], "promoted_to_gold": True, "supersedes_row_id": supersedes_row_id})
        return {"status": "pass", "dataset_id": dataset_id, "promoted_row": promoted_row}

    def run_eval(
        self,
        *,
        dataset_id: str,
        model_id: str,
        index_id: str = "",
        config_hash: str = "",
        threshold: float | None = None,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        dataset_path = self.paths.dataset_path(dataset_id)
        rows = _load_jsonl(dataset_path)
        dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest() if dataset_path.exists() else ""
        attorney_reviewed = sum(1 for row in rows if bool(row.get("attorney_reviewed")))
        synthetic_rows = sum(1 for row in rows if bool(row.get("synthetic")))
        seed_rows = sum(1 for row in rows if bool(row.get("seed")))
        private_training_rows = sum(1 for row in rows if row.get("private_data_allowed_for_training") is True)
        freshness_statuses = sorted({str(row.get("freshness_status") or "unknown") for row in rows})
        sample_size = len(rows)
        freshness_blocked = any(
            status.casefold() in {"stale", "unknown", "superseded", "retrieval_failed", "parser_failed"}
            for status in freshness_statuses
        )
        eligible = bool(rows) and not synthetic_rows and not seed_rows and not private_training_rows and attorney_reviewed > 0 and not freshness_blocked
        eligibility_reasons = []
        if not rows:
            eligibility_reasons.append("empty_dataset")
        if synthetic_rows:
            eligibility_reasons.append("synthetic_rows_present")
        if seed_rows:
            eligibility_reasons.append("seed_rows_present")
        if private_training_rows:
            eligibility_reasons.append("private_training_rows_present")
        if attorney_reviewed <= 0:
            eligibility_reasons.append("missing_attorney_review")
        if freshness_blocked:
            eligibility_reasons.append("freshness_not_current")
        measurement_basis = "attorney_reviewed_gold" if eligible else "blocked_until_real_attorney_reviewed_gold"
        metrics_report = ReleaseMetricsEvidenceBuilder(project_root=self.project_root, eval_root=self.layout.root).build()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run_record = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "model_id": model_id,
            "index_id": index_id,
            "config_hash": config_hash,
            "threshold": threshold,
            "sample_size": sample_size,
            "attorney_reviewed_count": attorney_reviewed,
            "synthetic_rows": synthetic_rows,
            "seed_rows": seed_rows,
            "private_training_rows": private_training_rows,
            "freshness_statuses": freshness_statuses,
            "eligible": eligible,
            "eligibility_reasons": eligibility_reasons,
            "measurement_basis": measurement_basis,
            "started_at": _now(),
            "status": "running",
        }
        _append_jsonl(self.paths.runs_ledger_path, {"event_type": "run_started", **run_record})
        _write_json(self.paths.run_path(run_id), run_record)
        metrics_payload = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "model_id": model_id,
            "index_id": index_id,
            "config_hash": config_hash,
            "threshold": threshold,
            "sample_size": sample_size,
            "attorney_reviewed_count": attorney_reviewed,
            "eligible": eligible,
            "freshness_statuses": freshness_statuses,
            "eligibility_reasons": eligibility_reasons,
            "measurement_basis": measurement_basis,
            "metrics": metrics_report.as_dict().get("metrics", []),
            "generated_at": _now(),
        }
        comparison = self._compare_to_last_accepted_release(metrics_payload)
        failure_clusters = self._failure_clusters(rows)
        result = {
            "status": "pass",
            "run": run_record,
            "metrics": metrics_payload,
            "failure_clusters": failure_clusters,
            "release_comparison": comparison,
            "metrics_report": metrics_report.as_dict(),
        }
        _write_json(self.paths.metrics_path(run_id), metrics_payload)
        _write_json(self.paths.failure_cluster_path(run_id), failure_clusters)
        _write_json(self.paths.release_comparison_path(run_id), comparison)
        result["export_bundle"] = self.export_review_bundle()
        if output_path:
            _write_json(Path(output_path), result)
        return result

    def cancel_run(self, run_id: str, *, reason: str = "") -> dict[str, Any]:
        run_path = self.paths.run_path(run_id)
        if not run_path.exists():
            raise EvalReviewStudioError("eval_run_not_found", f"Run not found: {run_id}", status_code=404)
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["status"] = "cancelled"
        run["cancelled_at"] = _now()
        run["cancel_reason"] = reason[:500]
        _write_json(run_path, run)
        _append_jsonl(self.paths.runs_ledger_path, {"event_type": "run_cancelled", "run_id": run_id, "cancelled_at": run["cancelled_at"], "reason": reason[:500]})
        return {"status": "pass", "run": run}

    def get_run(self, run_id: str) -> dict[str, Any]:
        run_path = self.paths.run_path(run_id)
        if not run_path.exists():
            raise EvalReviewStudioError("eval_run_not_found", f"Run not found: {run_id}", status_code=404)
        return json.loads(run_path.read_text(encoding="utf-8"))

    def metrics(self) -> dict[str, Any]:
        latest = self._latest_json(self.layout.metrics)
        if latest is None:
            return {"status": "blocked", "metrics": [], "blockers": ["no_evaluation_metrics_found"]}
        latest["honest_participation"] = self._honest_participation_report()
        return latest

    def failures(self) -> dict[str, Any]:
        latest = self._latest_json(self.layout.failure_clusters)
        if latest is None:
            return {"status": "blocked", "clusters": {}, "rows": []}
        return latest

    def release_comparison(self) -> dict[str, Any]:
        latest = self._latest_json(self.layout.release_comparisons)
        if latest is None:
            return {"status": "blocked", "comparison": "no_baseline"}
        return latest

    def export_review_bundle(self, *, output_dir: str | Path | None = None) -> dict[str, Any]:
        export_dir = Path(output_dir) if output_dir is not None else self.layout.exports
        export_dir.mkdir(parents=True, exist_ok=True)
        bundle = {
            "status": "pass",
            "generated_at": _now(),
            "eval_root": str(self.layout.root),
            "dataset_manifest": self.dataset_manifest(),
            "review_events": self._review_events(),
            "recusals": self._recusal_events(),
            "adjudications": _load_jsonl(self.paths.adjudications_path),
            "promotions": _load_jsonl(self.layout.promoted_gold / "promotions.jsonl"),
            "corrections": _load_jsonl(self.paths.corrections_path),
            "metrics": self.metrics(),
            "failure_clusters": self.failures(),
            "release_comparison": self.release_comparison(),
            "honest_participation": self._honest_participation_report(),
        }
        _write_json(export_dir / "dataset_manifest.json", bundle["dataset_manifest"])
        _write_json(export_dir / "attorney_review_evidence_summary.json", bundle["honest_participation"])
        _write_json(export_dir / "metrics.json", bundle["metrics"])
        _write_json(export_dir / "failure_clusters.json", bundle["failure_clusters"])
        _write_json(export_dir / "release_comparison.json", bundle["release_comparison"])
        _write_json(export_dir / "review_bundle.json", bundle)
        review_events_path = export_dir / "review_bundle.jsonl"
        with review_events_path.open("w", encoding="utf-8") as handle:
            for row in bundle["review_events"] + bundle["recusals"] + bundle["adjudications"] + bundle["promotions"] + bundle["corrections"]:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        bundle["review_bundle_jsonl"] = str(review_events_path)
        bundle["dataset_manifest_path"] = str(export_dir / "dataset_manifest.json")
        bundle["metrics_path"] = str(export_dir / "metrics.json")
        bundle["failure_clusters_path"] = str(export_dir / "failure_clusters.json")
        bundle["release_comparison_path"] = str(export_dir / "release_comparison.json")
        bundle["attorney_review_evidence_summary_path"] = str(export_dir / "attorney_review_evidence_summary.json")
        return bundle

    def datasets(self) -> dict[str, Any]:
        audit = GoldEvalPackAuditor(project_root=self.project_root, eval_root=self.layout.root).run()
        return {
            "status": "pass",
            "datasets": [status.as_dict() for status in audit.datasets],
            "blockers": audit.blockers,
            "readiness": audit.readiness,
            "honest_participation": self._honest_participation_report(),
        }

    def dataset_detail(self, dataset_id: str) -> dict[str, Any]:
        path = self.paths.dataset_path(dataset_id)
        rows = _load_jsonl(path)
        if not path.exists():
            raise EvalReviewStudioError("eval_dataset_not_found", f"Dataset not found: {dataset_id}", status_code=404)
        return {
            "status": "pass",
            "dataset_id": dataset_id,
            "row_count": len(rows),
            "dataset_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": [_safe_row_view(row) for row in rows[:100]],
            "blockers": [],
        }

    def _find_row(self, row_id: str) -> dict[str, Any] | None:
        for path in (self.paths.queue_path, *[self.paths.dataset_path(name) for name in DATASET_NAMES]):
            if not path.exists():
                continue
            for row in _load_jsonl(path):
                if str(row.get("row_id") or row.get("queue_id")) == str(row_id):
                    return row
        return None

    def _reviews_for(self, row_id: str) -> list[dict[str, Any]]:
        return [
            row
            for row in _load_jsonl(self.paths.reviews_path)
            if str(row.get("row_id")) == str(row_id)
            and str(row.get("event_type") or "first_review") in {"first_review", "second_review"}
        ]

    def _review_events(self) -> list[dict[str, Any]]:
        return [
            row
            for row in _load_jsonl(self.paths.reviews_path)
            if str(row.get("event_type") or "first_review") in {"first_review", "second_review"}
        ]

    def _recusal_events(self) -> list[dict[str, Any]]:
        return _load_jsonl(self.paths.recusals_path)

    def _has_disagreement(self, row_id: str, decision: str) -> bool:
        reviews = self._reviews_for(row_id)
        if len(reviews) < 2:
            return False
        decisions = {str(item.get("decision")) for item in reviews}
        return len(decisions) > 1 or decision not in decisions

    def _public_review_view(self, review: dict[str, Any]) -> dict[str, Any]:
        return {
            "row_id": review.get("row_id"),
            "reviewer_safe_id": review.get("reviewer_safe_id"),
            "reviewer_role": review.get("reviewer_role"),
            "decision": review.get("decision"),
            "confidence": review.get("confidence"),
            "rationale_summary": review.get("rationale_summary"),
            "blind": review.get("blind"),
            "reviewed_at": review.get("reviewed_at"),
        }

    def _row_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        reviews = [self._public_review_view(item) for item in self._reviews_for(str(row.get("row_id") or row.get("queue_id")))]
        adjudications = [item for item in _load_jsonl(self.paths.adjudications_path) if str(item.get("row_id")) == str(row.get("row_id") or row.get("queue_id"))]
        recusals = [item for item in self._recusal_events() if str(item.get("row_id")) == str(row.get("row_id") or row.get("queue_id"))]
        corrections = [item for item in _load_jsonl(self.paths.corrections_path) if str(item.get("row_id")) == str(row.get("row_id") or row.get("queue_id"))]
        payload = _safe_row_view(row)
        payload["reviews"] = reviews
        payload["adjudications"] = adjudications
        payload["recusals"] = recusals
        payload["corrections"] = corrections
        payload["history"] = {
            "review_count": len(reviews),
            "adjudication_count": len(adjudications),
            "recusal_count": len(recusals),
            "correction_count": len(corrections),
        }
        return payload

    def dataset_manifest(self) -> dict[str, Any]:
        datasets = []
        for dataset_id in DATASET_NAMES:
            path = self.paths.dataset_path(dataset_id)
            rows = _load_jsonl(path)
            datasets.append(
                {
                    "dataset_id": dataset_id,
                    "exists": path.exists(),
                    "row_count": len(rows),
                    "attorney_reviewed_rows": sum(1 for row in rows if bool(row.get("attorney_reviewed"))),
                    "synthetic_rows": sum(1 for row in rows if bool(row.get("synthetic"))),
                    "seed_rows": sum(1 for row in rows if bool(row.get("seed"))),
                    "private_training_rows": sum(1 for row in rows if row.get("private_data_allowed_for_training") is True),
                    "dataset_hash": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "",
                }
            )
        return {
            "status": "pass",
            "generated_at": _now(),
            "eval_root": str(self.layout.root),
            "datasets": datasets,
        }

    def _honest_participation_report(
        self,
        *,
        reviews: list[dict[str, Any]] | None = None,
        recusals: list[dict[str, Any]] | None = None,
        adjudications: list[dict[str, Any]] | None = None,
        promotions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        reviews = reviews if reviews is not None else self._review_events()
        recusals = recusals if recusals is not None else self._recusal_events()
        adjudications = adjudications if adjudications is not None else _load_jsonl(self.paths.adjudications_path)
        promotions = promotions if promotions is not None else _load_jsonl(self.layout.promoted_gold / "promotions.jsonl")
        reviewer_ids = sorted({str(row.get("reviewer_safe_id") or "") for row in reviews if row.get("reviewer_safe_id")})
        attorney_review_events = sum(1 for row in reviews if "attorney" in str(row.get("reviewer_role", "")).casefold())
        return {
            "status": "pass" if (reviews or recusals or adjudications or promotions) else "blocked",
            "attorney_review_events": attorney_review_events,
            "review_event_count": len(reviews),
            "recusal_count": len(recusals),
            "adjudication_count": len(adjudications),
            "promotion_count": len(promotions),
            "reviewer_ids": reviewer_ids,
            "license_verification_status": "unknown",
            "notes": "Local events can confirm that attorney review roles were used, but they do not independently verify bar membership.",
        }

    def _eligibility_report(self, *, audit: Any, honest_participation: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "pass" if audit.production_ready and honest_participation.get("attorney_review_events", 0) > 0 else "blocked",
            "attorney_review_required": True,
            "gold_eval_pack_ready": bool(audit.production_ready),
            "attorney_review_events": honest_participation.get("attorney_review_events", 0),
            "blockers": list(audit.blockers)
            or ([] if honest_participation.get("attorney_review_events", 0) else ["no_attorney_review_events_observed"]),
        }

    def _latest_json(self, directory: Path) -> dict[str, Any] | None:
        files = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))

    def _compare_to_last_accepted_release(self, current: dict[str, Any]) -> dict[str, Any]:
        baseline_path = self.layout.release_comparisons / "last_accepted_release.json"
        if not baseline_path.exists():
            return {
                "status": "blocked",
                "comparison": "no_accepted_release_baseline",
                "baseline_present": False,
                "current": {
                    "run_id": current["run_id"],
                    "dataset_hash": current["dataset_hash"],
                    "attorney_reviewed_count": current["attorney_reviewed_count"],
                },
            }
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current_metrics = {str(item.get("name")): item for item in current.get("metrics", []) if isinstance(item, dict)}
        baseline_metrics = {str(item.get("name")): item for item in baseline.get("metrics", []) if isinstance(item, dict)}
        deltas: dict[str, Any] = {}
        for name, item in current_metrics.items():
            if name not in baseline_metrics:
                continue
            current_value = item.get("value")
            baseline_value = baseline_metrics[name].get("value")
            if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float)):
                deltas[name] = current_value - baseline_value
        return {
            "status": "pass",
            "comparison": "baseline_present",
            "baseline_present": True,
            "baseline_run_id": baseline.get("run_id"),
            "deltas": deltas,
            "current": {
                "run_id": current["run_id"],
                "dataset_hash": current["dataset_hash"],
                "attorney_reviewed_count": current["attorney_reviewed_count"],
            },
        }

    def _failure_clusters(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        clusters: dict[str, int] = {}
        by_source_class: dict[str, int] = {}
        by_freshness: dict[str, int] = {}
        failure_rows: list[dict[str, Any]] = []
        for row in rows:
            if row.get("review_status") in {"needs_attorney_review", "queued"}:
                continue
            failure_code = str(row.get("failure_code") or row.get("conflict_status") or row.get("review_status") or "unknown")
            clusters[failure_code] = clusters.get(failure_code, 0) + 1
            source_class = str(row.get("source_class") or "unknown")
            freshness = str(row.get("freshness_status") or "unknown")
            by_source_class[source_class] = by_source_class.get(source_class, 0) + 1
            by_freshness[freshness] = by_freshness.get(freshness, 0) + 1
            failure_rows.append(
                {
                    "row_id": row.get("row_id") or row.get("queue_id"),
                    "dataset_type": row.get("dataset_type") or row.get("promoted_gold_dataset"),
                    "source_id": row.get("source_id"),
                    "source_span": row.get("source_span"),
                    "failure_code": failure_code,
                    "regression_status": row.get("regression_status", "unknown"),
                    "owner_status": row.get("owner_status", ""),
                    "fixed_in_version": row.get("fixed_in_version", ""),
                    "release_blocker": bool(row.get("release_blocker")),
                }
            )
        return {
            "status": "pass" if failure_rows else "empty",
            "generated_at": _now(),
            "clusters": clusters,
            "clusters_by_source_class": dict(sorted(by_source_class.items())),
            "clusters_by_freshness": dict(sorted(by_freshness.items())),
            "rows": failure_rows,
        }
