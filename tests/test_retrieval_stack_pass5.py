from legal.evals.retrieval_metrics import summarize_ranked_retrieval
from legal.retrieval import RetrievalDocument, RetrievalPipeline
from legal.retrieval.hybrid_search import HybridSearch
from legal.retrieval.lexical_search import BM25LexicalSearch
from legal.retrieval.query_expansion import expand_query_guarded
from legal.verifiers import SourceAuthorityIndex


def sample_documents():
    return [
        RetrievalDocument(
            source_id="source-statute-19a-1653",
            document_id="statute-19a-1653",
            title="19-A M.R.S. § 1653: Parental rights and responsibilities",
            citation="19-A M.R.S. § 1653",
            text="Parental rights and responsibilities are determined by the best interest of the child, including primary residence and contact.",
            source_class="statute_section",
            authority_status="verified_official_maine",
            freshness_status="current",
            issue_labels=("parental_rights_responsibilities", "primary_residence", "contact_schedule"),
        ),
        RetrievalDocument(
            source_id="source-rule-120",
            document_id="rule-120",
            title="M.R. Civ. P. 120 findings order",
            citation="M.R. Civ. P. 120",
            text="Family matter findings must be sufficient for appellate review.",
            source_class="court_rule",
            authority_status="verified_official_maine",
            freshness_status="current",
            issue_labels=("Rule_52_findings",),
        ),
        RetrievalDocument(
            source_id="source-form-fm-002",
            document_id="form-fm-002",
            title="Family Matter Summary Sheet FM-002",
            citation="FM-002",
            text="Official Maine Judicial Branch family matter summary sheet form.",
            source_class="court_form",
            authority_status="verified_official_maine",
            freshness_status="known",
            issue_labels=("divorce",),
        ),
        RetrievalDocument(
            source_id="public-summary-1653",
            document_id="summary-1653",
            title="Custody overview",
            text="A public custody summary discusses best interest and visitation.",
            source_class="public_non_official_source",
            authority_status="verified_public_api",
            freshness_status="unknown",
            issue_labels=("parental_rights_responsibilities",),
        ),
    ]


def test_exact_statute_query_retrieves_exact_section_first():
    results = BM25LexicalSearch().search("19-A M.R.S. § 1653", sample_documents(), top_k=5)
    assert results[0].source_id == "source-statute-19a-1653"
    assert results[0].component_scores["exact_citation"] > 0


def test_hybrid_retrieval_prefers_official_authority_over_public_summary():
    results = HybridSearch().search("custody best interest visitation", sample_documents(), top_k=4)
    source_ids = [result.source_id for result in results]
    assert "source-statute-19a-1653" in source_ids
    assert "public-summary-1653" in source_ids
    assert source_ids.index("source-statute-19a-1653") < source_ids.index("public-summary-1653")
    assert results[0].method == "hybrid_rrf_authority_weighted"


def test_retrieval_pipeline_returns_source_cards_and_citation_resolution_context():
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-19a-1653")
    pipeline = RetrievalPipeline(sample_documents(), authority_index=index)
    response = pipeline.retrieve("What does 19-A M.R.S. § 1653 say about custody?", top_k=2)
    assert response["retrieved_sources"][0]["source_card"]["source_id"] == "source-statute-19a-1653"
    assert response["source_cards"][0]["authority_status"] == "verified_official_maine"
    assert response["citation_resolution_context"][0]["status"] == "found"
    assert response["review_required"] is True


def test_form_id_lookup_retrieves_official_form():
    results = HybridSearch().search("FM-002 family matter form", sample_documents(), top_k=3)
    assert results[0].source_id == "source-form-fm-002"


def test_retrieval_metrics_include_recall_mrr_and_ndcg():
    metrics = summarize_ranked_retrieval(
        ["source-statute-19a-1653", "public-summary-1653"],
        {"source-statute-19a-1653"},
        ks=(1, 2, 5),
    )
    assert metrics["recall_at_1"] == 1.0
    assert metrics["precision_at_1"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg_at_2"] == 1.0


def test_query_expansion_keeps_non_maine_jurisdiction_out_of_maine_synonyms():
    receipt = expand_query_guarded("What New Hampshire custody rule applies?")
    assert receipt.jurisdiction_status == "non_maine_review_required"
    assert receipt.expansion_applied is False
    assert "parental" not in receipt.terms
    assert "jurisdiction_review_required" in receipt.guardrails


def test_query_expansion_preserves_exact_maine_form_reference():
    receipt = expand_query_guarded("Where can I find Maine FM-002 form?")
    assert receipt.exact_reference_preserved is True
    assert "fm-002" in receipt.terms
    assert receipt.receipt()["review_required"] is True
