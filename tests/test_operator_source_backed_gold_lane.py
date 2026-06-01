from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.evals.claim_support_metrics import ClaimSupportMetricRunner
from legal.evals.citation_quote_metrics import CitationQuoteVerifierMetricRunner

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _fixture_external_authority(tmp_path: Path) -> tuple[Path, Path, Path]:
    parsed_root = tmp_path / "parsed_authority_store"
    authority_index = tmp_path / "authority_layer" / "citation_index.json"
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        parsed_root / "statutes" / "title19a.jsonl",
        [
            {
                "source_id": "statute-19a-1653",
                "record_id": "statute-19a-1653",
                "source_class": "statute",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "citation": "19-A M.R.S. § 1653",
                "authority_status": "verified_official_maine",
                "text": "Maine law provides that parental rights and responsibilities are decided according to the best interest of the child. The court reviews relevant statutory factors.",
            }
        ],
    )
    _write_json(
        authority_index,
        [
            {
                "source_id": "statute-19a-1653",
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "authority_status": "verified_official_maine",
                "metadata": {"jurisdiction": "maine"},
            }
        ],
    )
    return parsed_root, authority_index, eval_root


def test_operator_source_backed_pack_builds_rows_and_passes_pass29_pass30(tmp_path: Path) -> None:
    parsed_root, authority_index, eval_root = _fixture_external_authority(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-operator-source-backed-gold-pack.py",
            "--eval-root",
            str(eval_root),
            "--parsed-authority-root",
            str(parsed_root),
            "--authority-index",
            str(authority_index),
            "--limit",
            "10",
            "--overwrite",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    manifest = json.loads((eval_root / "operator_source_backed_gold_pack_manifest.json").read_text())
    assert manifest["status"] == "pass"
    assert manifest["review_mode"] == "operator_source_backed"
    assert manifest["attorney_reviewed"] is False
    assert manifest["operator_source_backed"] is True

    pass29 = CitationQuoteVerifierMetricRunner(review_mode="operator_source_backed").run(
        eval_root=eval_root,
        authority_index_path=authority_index,
        parsed_authority_root=parsed_root,
    ).as_dict()
    assert pass29["status"] == "pass"
    assert pass29["review_mode"] == "operator_source_backed"
    assert pass29["citation_operator_source_backed_rows"] == pass29["citation_total"]
    assert pass29["quote_operator_source_backed_rows"] == pass29["quote_total"]
    assert pass29["release_metric_measurements"][0]["operator_source_backed"] is True

    pass30 = ClaimSupportMetricRunner(review_mode="operator_source_backed").run(
        eval_root=eval_root,
        parsed_authority_root=parsed_root,
    ).as_dict()
    assert pass30["status"] == "pass"
    assert pass30["review_mode"] == "operator_source_backed"
    assert pass30["claim_operator_source_backed_rows"] == pass30["claim_total"]
    assert pass30["release_metric_measurements"][0]["operator_source_backed"] is True


def test_operator_source_backed_audits_accept_operator_rows(tmp_path: Path) -> None:
    pass29_metrics = tmp_path / "pass29.json"
    pass29_metrics.write_text(
        json.dumps(
            {
                "status": "pass",
                "citation_existence": 1.0,
                "quote_span_verification": 1.0,
                "citation_total": 1,
                "quote_total": 1,
                "citation_attorney_reviewed_rows": 0,
                "quote_attorney_reviewed_rows": 0,
                "citation_operator_source_backed_rows": 1,
                "quote_operator_source_backed_rows": 1,
                "citation_seed_or_synthetic_rows": 0,
                "quote_seed_or_synthetic_rows": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    result29 = subprocess.run(
        [
            sys.executable,
            "scripts/audit-pass29-verifier-production.py",
            "--metrics",
            str(pass29_metrics),
            "--review-mode",
            "operator_source_backed",
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result29.returncode == 0, result29.stdout + result29.stderr

    pass30_metrics = tmp_path / "pass30.json"
    pass30_metrics.write_text(
        json.dumps(
            {
                "status": "pass",
                "citation_support": 1.0,
                "claim_total": 1,
                "claim_attorney_reviewed_rows": 0,
                "claim_operator_source_backed_rows": 1,
                "claim_seed_or_synthetic_rows": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    result30 = subprocess.run(
        [
            sys.executable,
            "scripts/audit-pass30-claim-support-production.py",
            "--metrics",
            str(pass30_metrics),
            "--review-mode",
            "operator_source_backed",
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result30.returncode == 0, result30.stdout + result30.stderr


def test_operator_source_backed_builder_matches_index_source_ids_to_parsed_citations(tmp_path: Path) -> None:
    parsed_root = tmp_path / "parsed_authority_store"
    authority_index = tmp_path / "authority_layer" / "citation_index.json"
    eval_root = tmp_path / "eval_store"
    _write_jsonl(
        parsed_root / "statutes" / "title19a.jsonl",
        [
            {
                "source_id": "parsed-title-19a-section-1653",
                "record_id": "parsed-title-19a-section-1653",
                "source_class": "statute",
                "jurisdiction": "maine",
                "citation": "19-A M.R.S. § 1653",
                "text": "The court shall apply the best interest of the child standard when allocating parental rights and responsibilities.",
            }
        ],
    )
    _write_json(
        authority_index,
        [
            {
                "source_id": "authority-index-row-873",
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "authority_status": "verified_official_maine",
                "metadata": {"jurisdiction": "maine"},
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-operator-source-backed-gold-pack.py",
            "--eval-root",
            str(eval_root),
            "--parsed-authority-root",
            str(parsed_root),
            "--authority-index",
            str(authority_index),
            "--limit",
            "10",
            "--overwrite",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    # No forms are present in this narrow fixture, so the manifest is allowed to block;
    # the regression target is that citation/quote/scope rows are no longer empty when
    # authority-index source IDs differ from parsed-authority record IDs.
    manifest = json.loads((eval_root / "operator_source_backed_gold_pack_manifest.json").read_text())
    assert manifest["counts"]["citation_claim_rows"] == 1, result.stdout + result.stderr
    assert manifest["counts"]["quote_rows"] == 1
    assert manifest["counts"]["scope_rows"] == 1
    quote_row = json.loads((eval_root / "maine_quote_span_gold.jsonl").read_text().splitlines()[0])
    assert quote_row["source_id"] == "parsed-title-19a-section-1653"
