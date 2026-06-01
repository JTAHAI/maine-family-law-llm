from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.staleness_jurisdiction_metrics import StalenessJurisdictionMetricRunner

ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _operator_row(**overrides):
    row = {
        "review_mode": "operator_source_backed",
        "review_status": "operator_source_backed",
        "reviewer_status": "operator_source_backed",
        "annotator_or_generation_method": "operator_source_backed_from_verified_authority",
        "operator_source_backed": True,
        "source_backed": True,
        "private_data_allowed_for_training": False,
    }
    row.update(overrides)
    return row


def test_pass31_metric_runner_passes_operator_source_backed_scope_and_forms(tmp_path: Path) -> None:
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_staleness_jurisdiction_gold.jsonl",
        [
            _operator_row(
                source_id="fresh-statute",
                answer_text="Current Maine law uses this source-backed statute check.",
                source_metadata=[
                    {
                        "source_id": "fresh-statute",
                        "source_class": "statute",
                        "jurisdiction": "maine",
                        "freshness_status": "fresh",
                        "authority_status": "verified_official_maine",
                        "negative_treatment_status": "known_clean",
                    }
                ],
                expected_status="verified_scope",
            ),
            _operator_row(
                source_id="stale-statute",
                answer_text="Current Maine law uses this stale source.",
                source_metadata=[
                    {
                        "source_id": "stale-statute",
                        "source_class": "statute",
                        "jurisdiction": "maine",
                        "freshness_status": "stale",
                        "authority_status": "verified_official_maine",
                    }
                ],
                expected_status="stale_or_unknown_freshness",
            ),
            _operator_row(
                source_id="nh-case",
                answer_text="This asks for Maine family law but cites New Hampshire authority.",
                source_metadata=[
                    {
                        "source_id": "nh-case",
                        "source_class": "case",
                        "jurisdiction": "new_hampshire",
                        "freshness_status": "fresh",
                        "authority_status": "verified_public_api",
                    }
                ],
                expected_status="jurisdiction_mismatch",
            ),
            _operator_row(
                source_id="case-treatment-unknown",
                answer_text="This Maine case has treatment that needs checking.",
                source_metadata=[
                    {
                        "source_id": "case-treatment-unknown",
                        "source_class": "case",
                        "jurisdiction": "maine",
                        "freshness_status": "fresh",
                        "authority_status": "verified_maine_law_court",
                        "negative_treatment_status": "negative_treatment_unknown",
                    }
                ],
                expected_status="negative_treatment_unknown",
            ),
        ],
    )
    _write_jsonl(
        eval_root / "maine_forms_freshness_gold.jsonl",
        [
            _operator_row(
                source_id="form-fm-001",
                source_class="court_form",
                jurisdiction="maine",
                form_id="FM-001",
                title="FM-001 Family Matter Summons",
                text_span="FM-001 Family Matter Summons Rev. 01/2026",
                version_date="01/2026",
                current_version_date="01/2026",
                expected_freshness_status="current",
            ),
            _operator_row(
                source_id="form-fm-002",
                source_class="court_form",
                jurisdiction="maine",
                form_id="FM-002",
                title="FM-002 Family Matter Summary Sheet",
                text_span="FM-002 Family Matter Summary Sheet Rev. 01/2025",
                version_date="01/2025",
                current_version_date="01/2026",
                expected_freshness_status="stale",
            ),
        ],
    )

    report = StalenessJurisdictionMetricRunner(review_mode="operator_source_backed").run(
        eval_root=eval_root,
        output_path=tmp_path / "staleness_jurisdiction_metrics.json",
        measurement_output_path=tmp_path / "release_metric_measurements.pass31.partial.json",
    ).as_dict()

    assert report["status"] == "pass"
    assert report["scope_verification"] == 1.0
    assert report["form_freshness_detection"] == 1.0
    assert report["scope_operator_source_backed_rows"] == report["scope_total"]
    assert report["form_operator_source_backed_rows"] == report["form_total"]
    measurements = json.loads((tmp_path / "release_metric_measurements.pass31.partial.json").read_text())
    assert {metric["name"] for metric in measurements["metrics"]} == {"scope_verification", "form_freshness_detection"}
    assert all(metric["operator_source_backed"] for metric in measurements["metrics"])


def test_pass31_metric_runner_blocks_seed_and_empty_inputs(tmp_path: Path) -> None:
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        eval_root / "maine_staleness_jurisdiction_gold.jsonl",
        [
            {
                "source_id": "seed-row",
                "answer_text": "Current Maine law uses this source.",
                "source_metadata": [{"source_id": "seed-row", "jurisdiction": "maine", "freshness_status": "fresh"}],
                "expected_status": "verified_scope",
                "review_status": "seed_not_attorney_reviewed",
                "annotator_or_generation_method": "synthetic_seed_for_schema_validation",
            }
        ],
    )

    report = StalenessJurisdictionMetricRunner(review_mode="operator_source_backed").run(eval_root=eval_root).as_dict()

    assert report["status"] == "blocked"
    assert "forms_freshness_gold_dataset_missing_or_empty" in report["blockers"]
    assert "scope_gold_contains_seed_or_synthetic_rows" in report["blockers"]


def test_pass31_audit_cli_accepts_operator_source_backed_report(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "status": "pass",
                "scope_verification": 1.0,
                "form_freshness_detection": 1.0,
                "scope_total": 2,
                "form_total": 2,
                "scope_operator_source_backed_rows": 2,
                "form_operator_source_backed_rows": 2,
                "scope_attorney_reviewed_rows": 0,
                "form_attorney_reviewed_rows": 0,
                "scope_seed_or_synthetic_rows": 0,
                "form_seed_or_synthetic_rows": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit-pass31-staleness-jurisdiction-production.py",
            "--metrics",
            str(metrics),
            "--review-mode",
            "operator_source_backed",
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"status": "pass"' in result.stdout
