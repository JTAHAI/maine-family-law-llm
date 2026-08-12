from legal.agent_runtime import ContextManifestBuilder, ContextSource, ProvenanceReceipt
from legal.drafting.provenance import validate_provenance_receipt
from legal.drafting.workspace import DraftWorkspaceBuilder


def _receipt():
    question = "Draft a review-required memo."
    manifest, _ = ContextManifestBuilder().build(
        question=question,
        sources=[ContextSource(source_id="s1", lane="legal_authority", title="Source", text="Source text")],
        run_id="draft-run",
        created_at="2026-07-27T00:00:00Z",
    )
    return ProvenanceReceipt.create(
        run_id="draft-run",
        question=question,
        manifest=manifest,
        answer="Draft answer [1]. Review required.",
        provider_id="ollama",
        model_id="local-model",
        endpoint_class="loopback_http",
        status="completed_review_required",
        citation_refs=[1],
        created_at="2026-07-27T00:00:01Z",
    ).to_dict()


def test_valid_receipt_is_hash_verified_for_draft_binding():
    report = validate_provenance_receipt(_receipt())
    assert report["status"] == "verified"
    assert report["verified"] is True
    assert report["source_role"] == "analytical_work_product_not_authority_or_evidence"


def test_tampered_receipt_fails_closed():
    receipt = _receipt()
    receipt["answer_sha256"] = "0" * 64
    report = validate_provenance_receipt(receipt)
    assert report["status"] == "invalid"
    assert "provenance_receipt_hash_mismatch" in report["blockers"]


def test_draft_workspace_carries_generation_provenance_sidebar():
    workspace = DraftWorkspaceBuilder().build(
        template_id="motion",
        issue_type="contempt",
        facts=["An order exists."],
        authorities=[],
        provenance_receipt=_receipt(),
    ).to_dict()
    assert workspace["draft"]["generation_provenance"]["verified"] is True
    assert workspace["sidebars"]["generation_provenance"]["receipt"]["provider_id"] == "ollama"
    assert workspace["review_required"] is True
