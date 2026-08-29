from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.claim_support_metrics import ClaimSupportMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _strict_row(*, claim: str, expected_status: str, **extra: object) -> dict:
    return {
        "claim": claim,
        "source_id": "official_maine_fixture",
        "expected_status": expected_status,
        "review_status": "attorney_reviewed_final",
        "annotator_or_generation_method": "attorney_review",
        "issue_labels": ["family_law"],
        "authority_build_id": "fictional_authority_build_001",
        "source_snapshot_sha256": "a" * 64,
        "reviewer_evidence_sha256": "b" * 64,
        "license_status": "license_verified_external",
        "source_freshness": "current",
        "jurisdiction": "maine",
        "authority_status": "verified_official_maine",
        **extra,
    }


def _strict_fixture(tmp_path: Path) -> tuple[Path, Path]:
    eval_root = tmp_path / "external_eval_root"
    source_texts = tmp_path / "external_source_texts.jsonl"
    authority = "Parental rights and responsibilities are decided according to the best interest of the child."
    _write_jsonl(
        eval_root / "maine_citation_validity_gold.jsonl",
        [
            _strict_row(claim=authority, expected_status="supported"),
            _strict_row(claim="Parental rights are decided according to custody preferences.", expected_status="partially_supported"),
            _strict_row(claim="Maine requires a purple parenting certificate in every custody case.", expected_status="unsupported"),
            _strict_row(claim="The court may not order contact.", expected_status="contradicted", evidence_text="The court may order contact."),
            _strict_row(claim="Best interest controls parental rights.", expected_status="stale", authority_status="stale_unknown"),
            _strict_row(claim="Best interest controls parental rights.", expected_status="jurisdiction_mismatch", jurisdiction="new_hampshire"),
            _strict_row(claim="!!!", expected_status="unknown"),
        ],
    )
    _write_jsonl(source_texts, [{"source_id": "official_maine_fixture", "text": authority}])
    return eval_root, source_texts


def test_pass183_strict_claim_benchmark_measures_each_required_state(tmp_path: Path) -> None:
    eval_root, source_texts = _strict_fixture(tmp_path)
    report = ClaimSupportMetricRunner().run(
        eval_root=eval_root,
        source_text_jsonl=source_texts,
        strict_provenance=True,
    ).as_dict()

    assert report["status"] == "pass", report
    assert report["claim_total"] == 7
    assert report["claim_correct"] == 7
    assert report["provenance_rows"] == 7
    assert all(report["status_metrics"][label]["sample_size"] == 1 for label in report["status_metrics"])
    assert report["actual_status_counts"]["not_verifiable"] == 1
    assert report["status_metrics"]["unknown"]["accuracy"] == 1.0


def test_pass183_production_route_requires_tenant_and_redacts_external_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.production import app

    eval_root, source_texts = _strict_fixture(tmp_path)
    monkeypatch.setenv("MFL_CLAIM_SUPPORT_EVAL_ROOT", str(eval_root))
    monkeypatch.setenv("MFL_CLAIM_SUPPORT_SOURCE_TEXT_JSONL", str(source_texts))
    client = TestClient(app)

    denied = client.get("/api/evals/claim-support/benchmark", headers={"X-User-Role": "reviewer"})
    assert denied.status_code == 403
    response = client.post(
        "/api/evals/claim-support/benchmark",
        headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["review_required"] is True
    assert payload["rbac"]["enforced"] is True
    assert str(tmp_path) not in json.dumps(payload)
    assert payload["status_metrics"]["unknown"]["sample_size"] == 1


def test_pass183_strict_mode_blocks_missing_provenance_and_missing_state_coverage(tmp_path: Path) -> None:
    eval_root, source_texts = _strict_fixture(tmp_path)
    rows = [json.loads(line) for line in (eval_root / "maine_citation_validity_gold.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0].pop("reviewer_evidence_sha256")
    _write_jsonl(eval_root / "maine_citation_validity_gold.jsonl", rows[:1])

    report = ClaimSupportMetricRunner().run(
        eval_root=eval_root,
        source_text_jsonl=source_texts,
        strict_provenance=True,
    ).as_dict()
    assert report["status"] == "blocked"
    assert "claim_reviewer_evidence_sha256_invalid" in report["blockers"]
    assert "claim_status_coverage_missing:unknown" in report["blockers"]
