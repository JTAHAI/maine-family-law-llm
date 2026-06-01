from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.claim_support_metrics import ClaimSupportMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_pass30_claim_support_metric_runner_passes_attorney_reviewed_gold(tmp_path: Path):
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [
            {
                "claim": "Maine decides parental rights according to the best interest of the child.",
                "source_id": "source-statute-1653",
                "expected_status": "supported",
                "review_status": "attorney_reviewed_final",
                "annotator_or_generation_method": "attorney_review",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
            },
            {
                "claim": "Maine requires a purple parenting certificate before contact.",
                "source_id": "source-statute-1653",
                "expected_status": "unsupported",
                "review_status": "attorney_reviewed_final",
                "annotator_or_generation_method": "attorney_review",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
            },
        ],
    )
    source_texts = tmp_path / "source_texts.jsonl"
    _write_jsonl(
        source_texts,
        [
            {
                "source_id": "source-statute-1653",
                "text": "Maine law provides that parental rights and responsibilities are decided according to the best interest of the child.",
            }
        ],
    )

    report = ClaimSupportMetricRunner().run(
        eval_root=eval_root,
        source_text_jsonl=source_texts,
        output_path=tmp_path / "pass30_metrics.json",
        measurement_output_path=tmp_path / "release_metric_measurements.pass30.partial.json",
    ).as_dict()

    assert report["status"] == "pass"
    assert report["citation_support"] == 1.0
    assert report["claim_attorney_reviewed_rows"] == report["claim_total"]
    measurement = json.loads((tmp_path / "release_metric_measurements.pass30.partial.json").read_text())
    assert measurement["metrics"][0]["name"] == "citation_support"
    assert measurement["metrics"][0]["value"] == 1.0


def test_pass30_claim_support_metric_runner_blocks_seed_and_missing_source_text(tmp_path: Path):
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [
            {
                "claim": "Maine decides parental rights according to the best interest of the child.",
                "source_id": "source-statute-1653",
                "expected_status": "supported",
                "review_status": "seed_not_attorney_reviewed",
                "annotator_or_generation_method": "synthetic_seed_for_schema_validation",
            }
        ],
    )

    report = ClaimSupportMetricRunner().run(eval_root=eval_root).as_dict()

    assert report["status"] == "blocked"
    assert "source_texts_missing" in report["blockers"]
    assert "claim_support_gold_contains_seed_or_synthetic_rows" in report["blockers"]


def test_pass30_claim_support_audit_cli_requires_ready_report(tmp_path: Path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "status": "pass",
                "citation_support": 1.0,
                "claim_total": 2,
                "claim_attorney_reviewed_rows": 2,
                "claim_seed_or_synthetic_rows": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit-pass30-claim-support-production.py",
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
