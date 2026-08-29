from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.citation_quote_metrics import CitationQuoteVerifierMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _strict_row(**extra: object) -> dict:
    return {
        "review_status": "attorney_reviewed_final",
        "annotator_or_generation_method": "attorney_review",
        "issue_labels": ["quote_verification"],
        "authority_build_id": "fictional_authority_build_001",
        "source_snapshot_sha256": "c" * 64,
        "reviewer_evidence_sha256": "d" * 64,
        "license_status": "license_verified_external",
        "source_freshness": "current",
        **extra,
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    eval_root = tmp_path / "external_eval_root"
    index = tmp_path / "external_authority_index.jsonl"
    source_texts = tmp_path / "external_source_texts.jsonl"
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [_strict_row(citation="19-A M.R.S. § 1653", expected_status="found", source_id="exact_source")],
    )
    _write_jsonl(
        eval_root / "maine_quote_span_gold.jsonl",
        [
            _strict_row(source_id="exact_source", quote="Exact source wording.", expected_decision="exact", parser_variant="native_pdf"),
            _strict_row(source_id="normalized_source", quote="the   best interest of the child.", expected_decision="normalized", parser_variant="ocr_pdf"),
            _strict_row(source_id="fuzzy_source", quote="court must make findings", expected_decision="fuzzy_review_required", parser_variant="docx"),
            _strict_row(source_id="mismatch_source", quote="This quote belongs to a different source.", expected_decision="mismatch", parser_variant="email_export"),
            _strict_row(source_id="not_found_source", quote="banana citation", expected_decision="not_found", parser_variant="scanned_pdf"),
        ],
    )
    _write_jsonl(index, [{"kind": "maine_statute", "normalized_citation": "19-A M.R.S. § 1653", "source_id": "exact_source"}])
    _write_jsonl(
        source_texts,
        [
            {"source_id": "exact_source", "text": "Exact source wording."},
            {"source_id": "normalized_source", "text": "The best interest of the child."},
            {"source_id": "fuzzy_source", "text": "The court must make sufficient findings."},
            {"source_id": "mismatch_source", "text": "A second source contains a different proposition."},
            {"source_id": "not_found_source", "text": "No matching language is present."},
        ],
    )
    return eval_root, index, source_texts


def test_pass184_strict_quote_benchmark_measures_parser_variants_and_review_states(tmp_path: Path) -> None:
    eval_root, index, source_texts = _fixture(tmp_path)
    report = CitationQuoteVerifierMetricRunner().run(
        eval_root=eval_root,
        authority_index_path=index,
        source_text_jsonl=source_texts,
        strict_provenance=True,
    ).as_dict()

    assert report["status"] == "pass", report
    assert report["quote_total"] == 5
    assert report["quote_correct"] == 5
    assert report["quote_provenance_rows"] == 5
    assert report["quote_actual_decision_counts"]["normalized"] == 1
    assert report["quote_actual_decision_counts"]["fuzzy_review_required"] == 1
    assert all(metric["sample_size"] == 1 for metric in report["quote_decision_metrics"].values())


def test_pass184_production_route_requires_role_tenant_and_redacts_external_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.production import app

    eval_root, index, source_texts = _fixture(tmp_path)
    monkeypatch.setenv("MFL_QUOTE_BENCHMARK_EVAL_ROOT", str(eval_root))
    monkeypatch.setenv("MFL_QUOTE_BENCHMARK_AUTHORITY_INDEX", str(index))
    monkeypatch.setenv("MFL_QUOTE_BENCHMARK_SOURCE_TEXT_JSONL", str(source_texts))
    client = TestClient(app)
    denied = client.post("/api/evals/quote-verifier/benchmark", headers={"X-User-Role": "viewer", "X-Tenant-Id": "fictional_tenant"})
    assert denied.status_code == 403
    response = client.post("/api/evals/quote-verifier/benchmark", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["review_required"] is True
    assert payload["quote_decision_metrics"]["fuzzy_review_required"]["sample_size"] == 1
    assert str(tmp_path) not in json.dumps(payload)


def test_pass184_strict_mode_blocks_missing_parser_provenance_and_coverage(tmp_path: Path) -> None:
    eval_root, index, source_texts = _fixture(tmp_path)
    row = json.loads((eval_root / "maine_quote_span_gold.jsonl").read_text(encoding="utf-8").splitlines()[0])
    row.pop("parser_variant")
    _write_jsonl(eval_root / "maine_quote_span_gold.jsonl", [row])
    report = CitationQuoteVerifierMetricRunner().run(
        eval_root=eval_root,
        authority_index_path=index,
        source_text_jsonl=source_texts,
        strict_provenance=True,
    ).as_dict()
    assert report["status"] == "blocked"
    assert "quote_parser_variant_missing" in report["blockers"]
    assert "quote_decision_coverage_missing:not_found" in report["blockers"]
