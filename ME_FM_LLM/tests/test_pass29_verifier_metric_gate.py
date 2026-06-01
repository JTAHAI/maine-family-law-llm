from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.citation_quote_metrics import CitationQuoteVerifierMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_pass29_metric_runner_passes_attorney_reviewed_citation_and_quote_gold(tmp_path: Path):
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [
            {
                "citation": "19-A M.R.S. § 1653",
                "expected_status": "found",
                "source_id": "source-statute-1653",
                "review_status": "attorney_reviewed_final",
                "annotator_or_generation_method": "attorney_review",
            },
            {
                "citation": "99 M.R.S. § 9999",
                "expected_status": "not_found",
                "review_status": "attorney_reviewed_final",
                "annotator_or_generation_method": "attorney_review",
            },
        ],
    )
    _write_jsonl(
        eval_root / "maine_quote_span_gold.jsonl",
        [
            {
                "source_id": "source-statute-1653",
                "quote": "best interest of the child",
                "expected_status": "found",
                "review_status": "attorney_reviewed_final",
                "annotator_or_generation_method": "attorney_review",
            }
        ],
    )
    authority_index = tmp_path / "authority_index.jsonl"
    _write_jsonl(
        authority_index,
        [
            {
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "source-statute-1653",
                "authority_status": "verified_official_maine",
            }
        ],
    )
    source_texts = tmp_path / "source_texts.jsonl"
    _write_jsonl(
        source_texts,
        [
            {
                "source_id": "source-statute-1653",
                "text": "19-A M.R.S. § 1653 applies the best interest of the child standard.",
            }
        ],
    )

    report = CitationQuoteVerifierMetricRunner().run(
        eval_root=eval_root,
        authority_index_path=authority_index,
        source_text_jsonl=source_texts,
        output_path=tmp_path / "pass29_metrics.json",
        measurement_output_path=tmp_path / "release_metric_measurements.pass29.partial.json",
    ).as_dict()

    assert report["status"] == "pass"
    assert report["citation_existence"] == 1.0
    assert report["quote_span_verification"] == 1.0
    assert report["citation_attorney_reviewed_rows"] == report["citation_total"]
    assert report["quote_attorney_reviewed_rows"] == report["quote_total"]
    measurement = json.loads((tmp_path / "release_metric_measurements.pass29.partial.json").read_text())
    assert {metric["name"] for metric in measurement["metrics"]} == {
        "citation_existence",
        "quote_span_verification",
    }


def test_pass29_metric_runner_blocks_seed_rows_and_missing_source_text(tmp_path: Path):
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [
            {
                "citation": "19-A M.R.S. § 1653",
                "expected_status": "found",
                "source_id": "source-statute-1653",
                "review_status": "seed_not_attorney_reviewed",
                "annotator_or_generation_method": "synthetic_seed_for_schema_validation",
            }
        ],
    )
    _write_jsonl(
        eval_root / "maine_quote_span_gold.jsonl",
        [
            {
                "source_id": "source-statute-1653",
                "quote": "best interest of the child",
                "expected_status": "found",
                "review_status": "seed_not_attorney_reviewed",
                "annotator_or_generation_method": "synthetic_seed_for_schema_validation",
            }
        ],
    )
    authority_index = tmp_path / "authority_index.jsonl"
    _write_jsonl(
        authority_index,
        [
            {
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "source-statute-1653",
            }
        ],
    )

    report = CitationQuoteVerifierMetricRunner().run(
        eval_root=eval_root,
        authority_index_path=authority_index,
    ).as_dict()

    assert report["status"] == "blocked"
    assert "citation_gold_contains_seed_or_synthetic_rows" in report["blockers"]
    assert "quote_gold_contains_seed_or_synthetic_rows" in report["blockers"]
    assert "source_texts_missing" in report["blockers"]


def test_pass29_audit_cli_requires_ready_report(tmp_path: Path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "status": "pass",
                "citation_existence": 1.0,
                "quote_span_verification": 1.0,
                "citation_total": 1,
                "quote_total": 1,
                "citation_attorney_reviewed_rows": 1,
                "quote_attorney_reviewed_rows": 1,
                "citation_seed_or_synthetic_rows": 0,
                "quote_seed_or_synthetic_rows": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit-pass29-verifier-production.py",
            "--metrics",
            str(metrics),
            "--require-ready",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"status": "pass"' in result.stdout
