from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from legal.evals import ReviewedGoldAnnotationPromoter

ROOT = Path(__file__).resolve().parents[1]


def _reviewed_row(index: int, **overrides: object) -> dict:
    text_span = f"Maine gold span {index}"
    row = {
        "queue_id": f"queue-{index}",
        "task_type": "rag_retrieval",
        "promoted_gold_dataset": "maine_rag_retrieval_gold.jsonl",
        "source_id": f"source-{index}",
        "source_class": "law_court_opinion_pdf",
        "jurisdiction": "maine",
        "text_span": text_span,
        "label": {"expected_source_id": f"source-{index}", "query": f"query {index}"},
        "annotator_or_generation_method": "attorney_review",
        "confidence": 0.99,
        "hash": hashlib.sha256(text_span.encode()).hexdigest(),
        "created_at": "2026-06-01T00:00:00+00:00",
        "review_status": "attorney_reviewed_final",
        "private_data_allowed_for_training": False,
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_reviewed_gold_annotation_promoter_writes_only_attorney_reviewed_rows(tmp_path: Path) -> None:
    reviewed_queue = tmp_path / "gold_annotation_queue.reviewed.jsonl"
    _write_jsonl(
        reviewed_queue,
        [
            _reviewed_row(1),
            _reviewed_row(2, review_status="needs_attorney_review"),
            _reviewed_row(3, private_data_allowed_for_training=True),
        ],
    )

    report = ReviewedGoldAnnotationPromoter(project_root=ROOT).promote(
        reviewed_queue_path=reviewed_queue,
        eval_root=tmp_path / "eval_store",
        output_report_path=tmp_path / "eval_store" / "gold_promotion_report.json",
    ).as_dict()

    gold_path = tmp_path / "eval_store" / "maine_rag_retrieval_gold.jsonl"
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines()]

    assert report["status"] == "pass"
    assert report["eligible_rows"] == 1
    assert report["skipped_rows"] == 2
    assert report["written_rows"] == 1
    assert len(rows) == 1
    assert rows[0]["source_id"] == "source-1"
    assert rows[0]["private_data_allowed_for_training"] is False


def test_reviewed_gold_annotation_promoter_blocks_when_no_reviewed_rows(tmp_path: Path) -> None:
    reviewed_queue = tmp_path / "gold_annotation_queue.reviewed.jsonl"
    _write_jsonl(reviewed_queue, [_reviewed_row(1, review_status="needs_attorney_review")])

    report = ReviewedGoldAnnotationPromoter(project_root=ROOT).promote(
        reviewed_queue_path=reviewed_queue,
        eval_root=tmp_path / "eval_store",
        output_report_path=tmp_path / "eval_store" / "gold_promotion_report.json",
    ).as_dict()

    assert report["status"] == "blocked"
    assert "no_attorney_reviewed_gold_rows_to_promote" in report["blockers"]
    assert not (tmp_path / "eval_store" / "maine_rag_retrieval_gold.jsonl").exists()


def test_promote_reviewed_gold_annotations_cli_require_promoted(tmp_path: Path) -> None:
    reviewed_queue = tmp_path / "gold_annotation_queue.reviewed.jsonl"
    _write_jsonl(reviewed_queue, [_reviewed_row(1)])
    report_path = tmp_path / "eval_store" / "gold_promotion_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "promote-reviewed-gold-annotations.py"),
            "--reviewed-queue",
            str(reviewed_queue),
            "--eval-root",
            str(tmp_path / "eval_store"),
            "--output-report",
            str(report_path),
            "--require-promoted",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    assert report_path.exists()
    assert json.loads(completed.stdout)["written_rows"] == 1
