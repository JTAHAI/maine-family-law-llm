from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.attorney_retrieval_eval import run_attorney_retrieval_eval
from legal.retrieval.models import RetrievalDocument
from legal.retrieval.optional_backends import SQLiteHybridIndex, is_loopback_qdrant_url, optional_backend_status
from legal.retrieval.workbench import RetrievalWorkbenchError, RetrievalWorkbenchService, private_record_documents


def _docs():
    return [
        RetrievalDocument(
            source_id="statute-1653",
            document_id="statute-1653",
            title="Best interest of the child",
            text="The court shall consider the best interest of the child and relevant factors.",
            citation="19-A M.R.S. § 1653",
            source_class="statute",
            authority_status="verified_official_maine",
            freshness_status="current",
            issue_labels=("parental_rights_responsibilities",),
        ),
        RetrievalDocument(
            source_id="record-1",
            document_id="record-1",
            title="Parent message",
            text="The child changed schools on January 3, 2026.",
            source_class="private_record",
            authority_status="user_provided_only",
            freshness_status="unknown",
            metadata={"source_lane": "private_record"},
        ),
    ]


def test_embedded_index_prefers_exact_current_authority_and_explains_components():
    results, diagnostics = SQLiteHybridIndex(_docs()).search("19-A M.R.S. § 1653 best interest", top_k=5)
    assert results[0].source_id == "statute-1653"
    assert "lexical" in results[0].explanation
    assert "fts5" in results[0].component_scores
    assert diagnostics["lexical_backend"] == "sqlite_fts5"
    assert diagnostics["network_used"] is False
    assert diagnostics["semantic_backend"] in {"sqlite_vec", "deterministic_hash_dense_fallback"}


def test_qdrant_endpoint_must_be_explicit_loopback():
    assert is_loopback_qdrant_url("http://localhost:6333") is True
    assert is_loopback_qdrant_url("https://127.0.0.1:6333") is True
    assert is_loopback_qdrant_url("http://qdrant.example.com:6333") is False
    assert is_loopback_qdrant_url("file:///tmp/qdrant") is False
    assert is_loopback_qdrant_url("http://user:pass@localhost:6333") is False


def test_optional_status_does_not_install_or_enable_remote_services(monkeypatch):
    monkeypatch.delenv("MFL_QDRANT_URL", raising=False)
    status = optional_backend_status()
    assert status["automatic_installation"] is False
    assert status["automatic_model_download"] is False
    qdrant = next(row for row in status["backends"] if row["backend_id"] == "qdrant_loopback")
    assert qdrant["enabled"] is False


def test_private_record_conversion_keeps_lane_and_no_absolute_path():
    rows = private_record_documents([
        {
            "evidence_id": "ev-1",
            "title": "Message",
            "snippet": "The child changed schools.",
            "source_locator": "C:\\private\\matter\\message.pdf",
            "page_number": 2,
            "source_hash": "a" * 64,
        }
    ])
    assert len(rows) == 1
    payload = rows[0].to_dict()
    assert payload["source_class"] == "private_record"
    assert payload["metadata"]["source_lane"] == "private_record"
    assert "C:\\private" not in json.dumps(payload)


def test_workbench_search_separates_lanes_and_does_not_claim_truth(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    service = RetrievalWorkbenchService(case)
    result = service.search(
        "changed schools",
        private_records=[{"evidence_id": "ev-1", "title": "Message", "snippet": "The child changed schools on January 3."}],
        include_authority=False,
    )
    assert result["status"] == "pass"
    assert result["lane_counts"]["private_record"] == 1
    assert result["results"][0]["why_this_matched"]["source_lane"] == "private_record"
    assert "does not establish" in result["what_this_does_not_prove"]


def test_workbench_fails_closed_without_documents(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    result = RetrievalWorkbenchService(case).search("custody", include_authority=False, include_private_records=False)
    assert result["status"] == "blocked_no_indexed_documents"
    assert result["blockers"]


def test_attorney_eval_excludes_seed_synthetic_and_nonattorney_rows(tmp_path: Path):
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    rows = [
        {"query": "best interest", "relevant_source_ids": ["statute-1653"], "review_status": "attorney_reviewed_final", "annotator_or_generation_method": "attorney_annotation", "private_data_allowed_for_training": False},
        {"query": "seed", "relevant_source_ids": ["x"], "review_status": "seed_needs_review", "annotator_or_generation_method": "synthetic_seed", "private_data_allowed_for_training": False},
        {"query": "paralegal", "relevant_source_ids": ["x"], "review_status": "paralegal_reviewed", "annotator_or_generation_method": "manual", "private_data_allowed_for_training": False},
    ]
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    report = run_attorney_retrieval_eval(dataset, search=lambda query, limit: ["statute-1653"], min_attorney_rows=1)
    assert report.status == "pass"
    assert report.rows_seen == 3
    assert report.attorney_reviewed_rows == 1
    assert report.evaluated_rows == 1
    assert report.metrics["recall_at_20"] == 1.0


def test_attorney_eval_blocks_when_reviewed_minimum_missing(tmp_path: Path):
    dataset = tmp_path / "maine_rag_retrieval_gold.jsonl"
    dataset.write_text(json.dumps({"query": "x", "relevant_source_ids": ["x"], "review_status": "needs_attorney_review"}) + "\n", encoding="utf-8")
    report = run_attorney_retrieval_eval(dataset, search=lambda query, limit: [], min_attorney_rows=2)
    assert report.status == "blocked"
    assert "attorney_reviewed_minimum_not_met" in report.blockers


def test_workbench_requires_external_eval_and_authority_roots(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    with pytest.raises(RetrievalWorkbenchError, match="external evaluation root"):
        RetrievalWorkbenchService(case).evaluate_attorney_gold()


def test_qdrant_adapter_is_read_only_loopback_and_requires_approval():
    from types import SimpleNamespace
    from legal.retrieval.optional_backends import QdrantLoopbackReadOnlyAdapter, RetrievalBackendError

    calls = []
    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))
        def query_points(self, **kwargs):
            calls.append(("query", kwargs))
            return SimpleNamespace(points=[SimpleNamespace(id=1, score=0.91, payload={"source_id": "statute-1653", "source_class": "statute", "authority_status": "verified_official_maine", "freshness_status": "current"})])

    adapter = QdrantLoopbackReadOnlyAdapter(url="http://127.0.0.1:6333", client_factory=FakeClient)
    with pytest.raises(RetrievalBackendError, match="Explicit approval"):
        adapter.search(collection="maine_authority", query_vector=[0.1, 0.2], approved=False)
    rows = adapter.search(collection="maine_authority", query_vector=[0.1, 0.2], approved=True)
    assert rows[0]["source_id"] == "statute-1653"
    assert rows[0]["read_only"] is True
    assert calls[1][1]["with_vectors"] is False
    assert all(call[0] != "write" for call in calls)


def test_external_eval_adapters_cannot_certify_or_use_private_data():
    from legal.evals.external_adapters import admit_deepeval_run, external_eval_adapter_status

    status = external_eval_adapter_status()
    assert status["attorney_gold_remains_authoritative"] is True
    assert all(row["runtime_enabled"] is False for row in status["adapters"])
    blocked = admit_deepeval_run(developer_ci=True, dataset_attorney_reviewed=True, private_matter_data=True)
    assert blocked["status"] == "blocked"
    assert "private_matter_data_forbidden" in blocked["blockers"]
    assert blocked["can_certify_legal_correctness"] is False


def test_private_record_string_labels_are_single_bounded_labels():
    rows = private_record_documents([
        {
            "evidence_id": "ev-labels",
            "snippet": "The order concerns contact and school enrollment.",
            "issue_labels": "contact_schedule",
            "procedural_postures": "post_judgment, motion_to_enforce",
        }
    ])
    assert rows[0].issue_labels == ("contact_schedule",)
    assert rows[0].procedural_postures == ("post_judgment", "motion_to_enforce")


def test_external_roots_inside_source_tree_fail_closed(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    repo_root = Path(__file__).resolve().parents[1]
    service = RetrievalWorkbenchService(
        case,
        authority_data_root=repo_root / "external-authority-not-allowed",
        eval_root=repo_root / "eval_data",
    )
    status = service.status()
    assert status["authority_index_configured"] is False
    assert status["attorney_gold_dataset_configured"] is False
    assert "authority_data_root_inside_source_tree" in status["blockers"]
    assert "eval_root_inside_source_tree" in status["blockers"]
    with pytest.raises(RetrievalWorkbenchError, match="outside the source tree"):
        service.authority_documents()
    with pytest.raises(RetrievalWorkbenchError, match="outside the source tree"):
        service.evaluate_attorney_gold()
