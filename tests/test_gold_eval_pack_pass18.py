from __future__ import annotations

import hashlib
import json
from pathlib import Path

from legal.evals import GoldAnnotationQueueBuilder, GoldEvalPackAuditor


def _gold_row(index: int, *, review_status: str = "attorney_reviewed_final") -> dict:
    text_span = f"Example Maine legal span {index}"
    return {
        "source_id": f"source-{index}",
        "source_class": "statute_title_index",
        "jurisdiction": "maine",
        "text_span": text_span,
        "label": ["divorce"],
        "annotator_or_generation_method": "attorney_review",
        "confidence": 0.99,
        "hash": hashlib.sha256(text_span.encode()).hexdigest(),
        "created_at": "2026-05-16T00:00:00+00:00",
        "review_status": review_status,
        "private_data_allowed_for_training": False,
    }


def test_pass18_gold_eval_pack_blocks_seed_and_undersized_rows(tmp_path):
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    seed = _gold_row(1, review_status="seed_not_attorney_reviewed")
    seed["annotator_or_generation_method"] = "synthetic_seed_for_schema_validation"
    dataset.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    policy = {
        "version": "test-pass18",
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
        "required_gold_dataset_minimums": {"maine_rag_retrieval_gold.jsonl": 2},
    }

    report = GoldEvalPackAuditor(project_root=Path.cwd(), eval_root=tmp_path, policy=policy).run()

    assert report.production_ready is False
    assert "gold_rows_minimum_not_met:maine_rag_retrieval_gold.jsonl" in report.blockers
    status = report.datasets[0]
    assert status.rows == 1
    assert status.synthetic_or_seed_rows == 1
    assert status.attorney_reviewed_rows == 0


def test_pass18_gold_eval_pack_passes_valid_attorney_rows(tmp_path):
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    rows = [_gold_row(1), _gold_row(2)]
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    policy = {
        "version": "test-pass18",
        "attorney_review_required": True,
        "private_data_training_allowed": False,
        "required_fields": list(rows[0].keys()),
        "required_gold_dataset_minimums": {"maine_rag_retrieval_gold.jsonl": 2},
    }

    report = GoldEvalPackAuditor(project_root=Path.cwd(), eval_root=tmp_path, policy=policy).run()

    assert report.production_ready is True
    assert report.datasets[0].status == "pass"
    assert report.datasets[0].attorney_reviewed_rows == 2
    assert not report.blockers


def test_pass18_gold_annotation_queue_builder_creates_review_worklist(tmp_path):
    snapshot = tmp_path / "official_authority_store" / "source-1.html"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("source text", encoding="utf-8")
    manifest = [
        {
            "source_id": "source-1",
            "source_class": "statute_title_index",
            "jurisdiction": "maine",
            "hash": hashlib.sha256(b"source text").hexdigest(),
            "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
            "snapshot_path": str(snapshot),
            "parser_status": "parsed",
            "freshness_status": "known_extracted_timestamp",
        }
    ]
    manifest_path = tmp_path / "official_authority_store" / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = tmp_path / "eval_store" / "gold_annotation_queue.jsonl"
    policy = {
        "annotation_queue_task_types": ["rag_retrieval", "citation_validity", "quote_span"],
    }

    result = GoldAnnotationQueueBuilder(project_root=Path.cwd(), policy=policy).build_from_manifest(
        manifest_path=manifest_path,
        output_path=output_path,
        max_items_per_task_type=1,
    )
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["queue_rows"] == 3
    assert {row["task_type"] for row in rows} == {"rag_retrieval", "citation_validity", "quote_span"}
    assert all(row["review_status"] == "needs_attorney_review" for row in rows)
    assert all(row["private_data_allowed_for_training"] is False for row in rows)
