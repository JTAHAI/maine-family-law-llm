from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.main import app as api_app
from legal.evals import EvalReviewStudio
from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root


def _write_policy(project_root: Path) -> None:
    (project_root / "configs").mkdir(parents=True, exist_ok=True)
    (project_root / "configs" / "maine_gold_eval_pack_policy.json").write_text(
        json.dumps(
            {
                "version": "test-v640",
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
                "required_gold_dataset_minimums": {
                    "maine_rag_retrieval_gold.jsonl": 1,
                    "maine_citation_validity_gold.jsonl": 1,
                    "maine_quote_span_gold.jsonl": 1,
                    "maine_hallucination_negative_cases.jsonl": 1,
                    "maine_forms_freshness_gold.jsonl": 1,
                    "maine_drafting_review_gold.jsonl": 1,
                    "maine_issue_classification_gold.jsonl": 1,
                    "maine_posture_classification_gold.jsonl": 1,
                    "maine_authority_ranking_gold.jsonl": 1,
                    "maine_fact_to_evidence_gold.jsonl": 1,
                    "maine_law_court_holding_gold.jsonl": 1,
                    "maine_rule_52_gap_gold.jsonl": 1,
                },
                "annotation_queue_task_types": ["rag_retrieval", "citation_validity"],
            }
        ),
        encoding="utf-8",
    )


def _write_manifest(path: Path) -> Path:
    record = {
        "source_id": "statute-1653",
        "source_class": "statute_title_index",
        "jurisdiction": "maine",
        "hash": "a" * 64,
        "source_url_or_path": "https://legislature.maine.gov/statute-1653",
        "snapshot_path": "/tmp/statute-1653.html",
        "parser_status": "parsed",
        "freshness_status": "known_extracted_timestamp",
        "issue_labels": ["custody"],
        "posture_labels": ["post_judgment"],
        "question": "What controls best interest?",
        "expected_result": "best_interest",
    }
    manifest = path / "official_authority_store" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps([record]), encoding="utf-8")
    return manifest


def test_external_eval_root_rejects_repo_local_and_traversal_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    repo_local = project_root / "eval_store"
    with pytest.raises(ExternalEvalRootError) as excinfo:
        resolve_external_eval_root(repo_local, project_root=project_root)
    assert excinfo.value.code == "external_root_inside_source_repo"
    with pytest.raises(ExternalEvalRootError, match="traversal"):
        resolve_external_eval_root("..\\outside", project_root=project_root)


def test_external_eval_root_rejects_symlink(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = tmp_path / "external_target"
    target.mkdir()
    link_root = tmp_path / "eval_root_link"
    try:
        link_root.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable in this environment")
    with pytest.raises(ExternalEvalRootError) as excinfo:
        resolve_external_eval_root(link_root, project_root=project_root)
    assert excinfo.value.code == "external_eval_root_symlink_refused"


def test_review_studio_queue_review_adjudicate_promote_and_run(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_policy(project_root)
    manifest_path = _write_manifest(tmp_path)
    eval_root = tmp_path / "external_eval_store"

    studio = EvalReviewStudio(project_root=project_root, eval_root=eval_root)
    queue_summary = studio.build_queue(
        manifest_path=manifest_path,
        output_path=eval_root / "annotation_queue" / "gold_annotation_queue.jsonl",
        max_items_per_task_type=1,
        reviewer_ids=["rev-1", "rev-2"],
        seed="seed-1",
    )
    queue_rows = [json.loads(line) for line in (eval_root / "annotation_queue" / "gold_annotation_queue.jsonl").read_text(encoding="utf-8").splitlines()]
    row_id = queue_rows[0]["row_id"]

    assert queue_summary["queue_rows"] == 2
    assert all(row["review_status"] == "needs_attorney_review" for row in queue_rows)
    assert queue_rows[0]["private_data_allowed_for_training"] is False

    first_review = studio.review_row(
        row_id,
        reviewer_safe_id="rev-1",
        reviewer_role="attorney_reviewer",
        decision="accept",
        confidence=0.9,
        rationale="matches source span",
    )
    second_review = studio.second_review_row(
        row_id,
        reviewer_safe_id="rev-2",
        reviewer_role="attorney_reviewer",
        decision="revise",
        confidence=0.7,
        rationale="needs narrower span",
        blind=True,
    )
    adjudication = studio.adjudicate_row(
        row_id,
        adjudicator_safe_id="adjud-1",
        adjudication_status="resolved",
        resolution_label="accept",
        rationale="first review controls",
        fixed_in_version="v1.0.0",
    )
    promotion = studio.promote_row(
        row_id,
        adjudicator_safe_id="adjud-1",
        notes="accepted gold",
    )
    run = studio.run_eval(
        dataset_id="maine_rag_retrieval_gold.jsonl",
        model_id="local-model",
        index_id="local-index",
        config_hash="cfg-1",
        threshold=0.5,
    )
    cancelled = studio.cancel_run(run["run"]["run_id"], reason="stop")

    payload = studio.get_row(row_id)
    assert first_review["status"] == "pass"
    assert second_review["disagreement_detected"] is True
    assert adjudication["status"] == "pass"
    assert promotion["promoted_row"]["promoted_to_gold"] is True
    assert (eval_root / "maine_rag_retrieval_gold.jsonl").exists()
    assert run["metrics"]["dataset_id"] == "maine_rag_retrieval_gold.jsonl"
    assert run["release_comparison"]["status"] == "blocked"
    assert cancelled["run"]["status"] == "cancelled"
    assert payload["history"]["review_count"] == 2
    assert len(payload["adjudications"]) == 1


def test_eval_api_contracts_and_response_sanitization(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_policy(project_root)
    manifest_path = _write_manifest(tmp_path)
    eval_root = tmp_path / "external_eval_store"
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("MFL_EVAL_ROOT", str(eval_root))

    client = TestClient(api_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-a"}

    queue = client.post(
        "/api/evals/queue/build",
        headers=headers,
        json={
            "manifest_path": str(manifest_path),
            "output_path": str(eval_root / "annotation_queue" / "gold_annotation_queue.jsonl"),
            "max_items_per_task_type": 1,
            "reviewer_ids": ["rev-1", "rev-2"],
            "seed": "seed-1",
        },
    )
    assert queue.status_code == 200
    assert "output_path" not in json.dumps(queue.json())
    assert queue.json()["queue_rows"] == 2

    status = client.get("/api/evals/status", headers=headers)
    assert status.status_code == 200
    assert "eval_root" not in json.dumps(status.json())

    registered = set()
    for route in api_app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or not path.startswith("/api"):
            continue
        registered.add((next(iter(methods)), path))
    endpoints = EndpointInventory().compare_to_registered(registered)
    assert endpoints["status"] == "pass"
    assert not endpoints["missing"]
