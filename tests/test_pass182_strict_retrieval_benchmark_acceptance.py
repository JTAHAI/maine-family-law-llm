from __future__ import annotations

import json
from pathlib import Path

from legal.evals.attorney_retrieval_eval import run_attorney_retrieval_eval


HASH_A = "a" * 64
HASH_B = "b" * 64


def _row(**extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "query": "19-A M.R.S. § 1653",
        "query_kind": "exact_citation",
        "relevant_source_ids": ["statute_1653"],
        "review_status": "attorney_reviewed_final",
        "annotator_or_generation_method": "attorney_annotation",
        "private_data_allowed_for_training": False,
        "issue_labels": ["parental_rights_responsibilities"],
        "authority_build_id": "fictional_external_build_001",
        "source_snapshot_sha256": HASH_A,
        "reviewer_evidence_sha256": HASH_B,
        "license_status": "license_verified_external",
        "source_freshness": "current",
    }
    row.update(extra)
    return row


def test_pass182_strict_benchmark_records_issue_freshness_provenance_and_exact_citation_metrics(tmp_path: Path) -> None:
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    dataset.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    report = run_attorney_retrieval_eval(dataset, search=lambda _query, _limit: ["statute_1653"], strict_provenance=True)
    payload = report.to_dict()
    assert report.status == "pass"
    assert payload["issue_counts"] == {"parental_rights_responsibilities": 1}
    assert payload["freshness_counts"] == {"current": 1}
    assert payload["provenance_rows"] == 1
    assert payload["exact_citation_accuracy"] == 1.0
    assert payload["pinpoint_accuracy"] is None
    assert payload["pinpoint_accuracy_status"] == "not_measured_by_source-id_retrieval_contract"


def test_pass182_strict_benchmark_blocks_missing_provenance_license_or_freshness(tmp_path: Path) -> None:
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    dataset.write_text(json.dumps(_row(issue_labels=[], source_freshness="stale", license_status="unknown", reviewer_evidence_sha256="")) + "\n", encoding="utf-8")
    report = run_attorney_retrieval_eval(dataset, search=lambda _query, _limit: ["statute_1653"], strict_provenance=True)
    assert report.status == "blocked"
    assert report.provenance_rows == 0
    assert any(blocker.startswith("missing_issue_labels") for blocker in report.blockers)
    assert any(blocker.startswith("missing_reviewer_evidence_sha256") for blocker in report.blockers)
    assert any(blocker.startswith("license_status_not_verified") for blocker in report.blockers)
    assert any(blocker.startswith("source_freshness_not_current") for blocker in report.blockers)
