from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.main import app as api_app
from app.web.ui_contracts import UICompletionAuditor
from legal.evals import EvalReviewStudio


DATASET_TYPES = (
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


def _write_policy(project_root: Path) -> None:
    (project_root / "configs").mkdir(parents=True, exist_ok=True)
    (project_root / "configs" / "maine_gold_eval_pack_policy.json").write_text(
        json.dumps(
            {
                "version": "test-v651",
                "attorney_review_required": True,
                "private_data_training_allowed": False,
                "required_fields": [
                    "source_id",
                    "source_class",
                    "jurisdiction",
                    "text_span",
                    "label",
                    "annotator_or_generation_method",
                    "confidence",
                    "hash",
                    "created_at",
                    "review_status",
                    "private_data_allowed_for_training",
                ],
                "required_gold_dataset_minimums": {dataset: 1 for dataset in DATASET_TYPES},
                "annotation_queue_task_types": [
                    "rag_retrieval",
                    "citation_validity",
                    "quote_span",
                    "hallucination_negative",
                    "forms_freshness",
                    "drafting_review",
                    "issue_classification",
                    "posture_classification",
                    "authority_ranking",
                    "fact_to_evidence",
                    "law_court_holding",
                    "rule_52_gap",
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_manifest(manifest_root: Path) -> Path:
    records = [
        {
            "source_id": "official-001",
            "source_class": "statute_title_index",
            "jurisdiction": "maine",
            "authority_build_id": "build-001",
            "hash": "a" * 64,
            "source_url_or_path": "https://legislature.maine.gov/statutes/19-A/title19-Asec1653.html",
            "snapshot_path": "/tmp/official-001.html",
            "source_span": {"start": 0, "end": 120},
            "parser_status": "parsed",
            "freshness_status": "current",
            "issue_labels": ["custody", "support"],
            "posture_labels": ["post_judgment"],
            "question": "What controls the best-interest analysis?",
            "expected_result": "best_interest_factors",
            "accepted_labels": ["best_interest_factors"],
            "rejected_labels": ["unsupported"],
            "synthetic": False,
            "seed": False,
        },
        {
            "source_id": "official-002",
            "source_class": "court_rules_index",
            "jurisdiction": "maine",
            "authority_build_id": "build-001",
            "hash": "b" * 64,
            "source_url_or_path": "https://www.courts.maine.gov/rules/family-divorce.html",
            "snapshot_path": "/tmp/official-002.html",
            "source_span": {"start": 0, "end": 150},
            "parser_status": "parsed",
            "freshness_status": "current",
            "issue_labels": ["rule_52"],
            "posture_labels": ["final_order"],
            "question": "What findings are required for review?",
            "expected_result": "sufficient_findings",
            "accepted_labels": ["sufficient_findings"],
            "rejected_labels": ["unsupported"],
            "synthetic": False,
            "seed": False,
        },
    ]
    manifest = manifest_root / "official_authority_store" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _build_gold_pack(studio: EvalReviewStudio, manifest_path: Path, eval_root: Path) -> list[dict]:
    studio.build_queue(
        manifest_path=manifest_path,
        output_path=eval_root / "annotation_queue" / "gold_annotation_queue.jsonl",
        max_items_per_task_type=2,
        reviewer_ids=["attorney-1", "attorney-2"],
        double_review=True,
        include_fixture_candidates=False,
        seed="seed-v651",
    )
    rows = [json.loads(line) for line in (eval_root / "annotation_queue" / "gold_annotation_queue.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 24

    first_row = rows[0]
    first_dataset = first_row["dataset_type"]
    studio.review_row(
        first_row["row_id"],
        reviewer_safe_id="attorney-1",
        reviewer_role="attorney_reviewer",
        decision="accept",
        confidence=0.97,
        rationale="Matches the source span and citation.",
    )
    second_review = studio.second_review_row(
        first_row["row_id"],
        reviewer_safe_id="attorney-2",
        reviewer_role="attorney_reviewer",
        decision="revise",
        confidence=0.82,
        rationale="Needs a narrower quote span.",
        blind=True,
    )
    assert second_review["review"]["prior_reviews_visible_to_reviewer"] == []
    assert second_review["disagreement_detected"] is True
    studio.adjudicate_row(
        first_row["row_id"],
        adjudicator_safe_id="attorney-3",
        adjudication_status="resolved",
        resolution_label="accept",
        rationale="First review controls for this synthetic slice.",
        fixed_in_version="6.0.4.0",
    )
    studio.promote_row(
        first_row["row_id"],
        adjudicator_safe_id="attorney-3",
        notes="Accepted after adjudication.",
    )
    superseded = studio.supersede_row(
        first_row["row_id"],
        adjudicator_safe_id="attorney-3",
        rationale="Corrected span after adjudication.",
        corrected_labels=["best_interest_factors"],
        fixed_in_version="6.0.4.1",
        notes="Superseding correction for the accepted row.",
    )
    assert superseded["supersession"]["superseded_by_row_id"] != first_row["row_id"]

    second_row = rows[1]
    studio.record_recusal(
        second_row["row_id"],
        reviewer_safe_id="attorney-2",
        reviewer_role="attorney_reviewer",
        reason="Conflict with the source origin.",
        conflict_of_interest_note="Prior work on this source class.",
    )

    for row in rows[2:]:
        studio.review_row(
            row["row_id"],
            reviewer_safe_id="attorney-1",
            reviewer_role="attorney_reviewer",
            decision="accept",
            confidence=0.94,
            rationale="Matches the source span and expected result.",
        )
        studio.adjudicate_row(
            row["row_id"],
            adjudicator_safe_id="attorney-3",
            adjudication_status="resolved",
            resolution_label="accept",
            rationale="Accepted for the synthetic gold pack.",
            fixed_in_version="6.0.4.0",
        )
        studio.promote_row(
            row["row_id"],
            adjudicator_safe_id="attorney-3",
            notes="Accepted synthetic gold row.",
        )

    assert (eval_root / first_dataset).exists()
    return rows


def test_attorney_review_studio_records_review_flow_exports_and_metrics(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_policy(project_root)
    manifest_path = _write_manifest(tmp_path)
    eval_root = tmp_path / "external_eval_store"

    studio = EvalReviewStudio(project_root=project_root, eval_root=eval_root)
    rows = _build_gold_pack(studio, manifest_path, eval_root)
    row_id = rows[0]["row_id"]

    status = studio.status()
    datasets = {row["dataset_id"]: row for row in status["dataset_manifest"]["datasets"]}
    assert status["honest_participation"]["attorney_review_events"] > 0
    assert status["eligibility"]["status"] == "pass"
    assert status["recusals"] == 1
    assert status["superseded_rows"] == 1
    assert datasets["maine_rag_retrieval_gold.jsonl"]["attorney_reviewed_rows"] >= 1

    row = studio.get_row(row_id)
    assert row["history"]["review_count"] == 2
    assert row["history"]["recusal_count"] == 0
    assert len(row["adjudications"]) == 1
    assert len(row["corrections"]) == 1

    run = studio.run_eval(
        dataset_id="maine_rag_retrieval_gold.jsonl",
        model_id="local-model",
        index_id="local-index",
        config_hash="cfg-651",
        threshold=0.75,
    )
    assert run["run"]["eligible"] is True
    assert run["run"]["eligibility_reasons"] == []
    assert run["metrics"]["eligible"] is True
    assert run["metrics"]["freshness_statuses"] == ["current"]
    assert run["release_comparison"]["status"] == "blocked"
    assert run["export_bundle"]["honest_participation"]["attorney_review_events"] > 0

    export_bundle = studio.export_review_bundle(output_dir=eval_root / "exports")
    assert Path(export_bundle["review_bundle_jsonl"]).exists()
    assert Path(export_bundle["dataset_manifest_path"]).exists()
    assert Path(export_bundle["metrics_path"]).exists()
    assert Path(export_bundle["failure_clusters_path"]).exists()
    assert Path(export_bundle["release_comparison_path"]).exists()
    assert Path(export_bundle["attorney_review_evidence_summary_path"]).exists()

    metrics = studio.metrics()
    failures = studio.failures()
    comparison = studio.release_comparison()
    assert metrics["honest_participation"]["attorney_review_events"] > 0
    assert failures["status"] == "pass"
    assert "clusters_by_source_class" in failures
    assert comparison["status"] == "blocked"


def test_eval_studio_blocks_synthetic_seed_private_and_stale_rows(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_policy(project_root)
    eval_root = tmp_path / "external_eval_store"
    studio = EvalReviewStudio(project_root=project_root, eval_root=eval_root)

    dataset_path = eval_root / "maine_rag_retrieval_gold.jsonl"
    dataset_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source_id": "row-1",
                        "attorney_reviewed": False,
                        "synthetic": True,
                        "seed": True,
                        "private_data_allowed_for_training": True,
                        "freshness_status": "stale",
                        "review_status": "blocked",
                    }
                ),
                json.dumps(
                    {
                        "source_id": "row-2",
                        "attorney_reviewed": False,
                        "synthetic": False,
                        "seed": False,
                        "private_data_allowed_for_training": False,
                        "freshness_status": "unknown",
                        "review_status": "blocked",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    run = studio.run_eval(
        dataset_id="maine_rag_retrieval_gold.jsonl",
        model_id="local-model",
        index_id="local-index",
        config_hash="cfg-blocked",
    )
    assert run["run"]["eligible"] is False
    assert "synthetic_rows_present" in run["run"]["eligibility_reasons"]
    assert "seed_rows_present" in run["run"]["eligibility_reasons"]
    assert "private_training_rows_present" in run["run"]["eligibility_reasons"]
    assert "freshness_not_current" in run["run"]["eligibility_reasons"]
    assert run["run"]["freshness_statuses"] == ["stale", "unknown"]
    assert run["metrics"]["eligible"] is False
    assert run["metrics"]["attorney_reviewed_count"] == 0
    assert run["failure_clusters"]["clusters_by_freshness"]["stale"] == 1

    status = studio.status()
    assert status["honest_participation"]["status"] == "blocked"
    assert status["eligibility"]["status"] == "blocked"


def test_eval_api_and_ui_surface_the_review_studio(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_policy(project_root)
    manifest_path = _write_manifest(tmp_path)
    eval_root = tmp_path / "external_eval_store"
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("MFL_EVAL_ROOT", str(eval_root))

    client = TestClient(api_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-eval"}
    queue = client.post(
        "/api/evals/queue/build",
        headers=headers,
        json={
            "manifest_path": str(manifest_path),
            "output_path": str(eval_root / "annotation_queue" / "gold_annotation_queue.jsonl"),
            "max_items_per_task_type": 2,
            "reviewer_ids": ["attorney-1", "attorney-2"],
            "seed": "seed-v651",
        },
    )
    assert queue.status_code == 200
    assert queue.json()["queue_rows"] == 24
    queue_rows = [json.loads(line) for line in (eval_root / "annotation_queue" / "gold_annotation_queue.jsonl").read_text(encoding="utf-8").splitlines()]

    recusal = client.post(
        f"/api/evals/rows/{queue_rows[0]['row_id']}/recuse",
        headers=headers,
        json={"reviewer_safe_id": "attorney-2", "reviewer_role": "attorney_reviewer", "reason": "conflict"},
    )
    assert recusal.status_code == 200

    exports = client.post("/api/evals/exports/build", headers=headers, json={"output_dir": str(eval_root / "exports")})
    assert exports.status_code == 200
    assert exports.json()["status"] == "pass"

    latest = client.get("/api/evals/exports/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json()["honest_participation"]["license_verification_status"] == "unknown"

    status = client.get("/api/evals/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["honest_participation"]["attorney_review_events"] == 0

    registered = set()
    for route in api_app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and path.startswith("/api"):
                registered.add((method, path))
    endpoints = EndpointInventory().compare_to_registered(registered)
    assert endpoints["status"] == "pass"

    page = Path("app/web/pages/admin-eval-dashboard.tsx").read_text(encoding="utf-8")
    app_shell = Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    assert "data-attorney-eval-lab=\"visible\"" in page
    assert "data-eval-export-bundle=\"visible\"" in page
    assert "/admin/evals" in app_shell
    assert "id=\"eval-lab-title\"" in page

    ui = UICompletionAuditor("app/web/pages").audit().as_dict()
    assert ui["status"] == "pass"

    js = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror_js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert js == mirror_js
    assert "open_eval_review_studio" not in js
    assert "/admin/evals" not in js
