"""Fictional deterministic safety regressions, not model-quality certification."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from legal.agent_runtime import ContextSource, LocalAgentRunRequest, LocalAgentRuntime, LocalModelResponse
from legal.agent_runtime.providers import LoopbackEndpointPolicy
from legal.fast_interchange.evidence_output import verify_evidence_output


SOURCE = ContextSource(source_id="fictional-note", lane="private_record", title="Fictional title",
                       locator="fictional page 1", text="Only the March attachments subfolder was searched.")


@pytest.mark.parametrize("answer,sources,blocker", [
    ('The record says "A missed session." [1]', (), "specialist_source_references_required"),
    ('The record says "Fictional title" [1]', (SOURCE,), "evidence_review_quote_not_in_cited_record"),
    ('"HOST SOURCE STATUS: unknown" [1]', (SOURCE,), "evidence_review_quote_not_in_cited_record"),
    ('"Only April was searched." [1]', (SOURCE,), "evidence_review_quote_not_in_cited_record"),
    ('"Only the March attachments subfolder was searched." [9999]', (SOURCE,), "specialist_source_references_required"),
    ('"Only the March attachments subfolder was searched." [0]', (SOURCE,), "specialist_source_references_required"),
    ('"Only the March attachments subfolder was searched." [1]. Under 2099 ME 777, this is proven.', (SOURCE,), "evidence_review_legal_authority_not_verified"),
    ('"Only the March attachments subfolder was searched." [1]. 19-A M.R.S. § 99999 applies.', (SOURCE,), "evidence_review_legal_authority_not_verified"),
    ('All evidence supports the claim [1].', (SOURCE,), "evidence_review_exact_quote_required"),
    ('"Only the March attachments subfolder was searched." [1] and "unclosed', (SOURCE,), "evidence_review_malformed_quote"),
    ('"Only the March attachments subfolder was searched." [1]', (replace(SOURCE, lane="legal_authority"),), "evidence_review_private_records_required"),
    ('"Only the March attachments subfolder was searched.". A different claim [1]', (SOURCE,), "evidence_review_quote_not_in_cited_record"),
])
def test_bad_output_is_withheld(answer, sources, blocker):
    report = verify_evidence_output(answer, sources)
    assert report["status"] == "withheld"
    assert blocker in report["blockers"]


def test_exact_quotes_bind_to_the_cited_body_not_another_record():
    other = replace(SOURCE, source_id="fictional-other", text="The April folder was not searched.")
    assert verify_evidence_output('"The April folder was not searched." [1]', (SOURCE, other))["blockers"]
    answer = 'Compare "Only the March attachments subfolder was searched." [1] with “The April folder was not searched.” [2]. Review required.'
    report = verify_evidence_output(answer, (SOURCE, other))
    assert not report["blockers"]
    assert [row["source_id"] for row in report["source_spans"]] == [SOURCE.source_id, other.source_id]
    assert report["factual_claims_verified"] is False
    assert report["legal_claims_verified"] is False
    assert len(report["report_sha256"]) == 64


def test_whitespace_only_normalization_retains_original_offsets():
    source = replace(SOURCE, text="Header: Only the March\nattachments subfolder was searched.")
    report = verify_evidence_output('"Only the March attachments subfolder was searched." [1]', (source,))
    row = report["source_spans"][0]
    assert row["status"] == "whitespace_normalized"
    assert source.text[row["start_offset"]:row["end_offset"]].startswith("Only the March\n")
    assert not report["blockers"]


def run_answer(answer):
    client = SimpleNamespace(provider_id="fast_interchange_local", model_name="fictional-model",
                             model_binding={"capability": "evidence_review"},
                             endpoint=LoopbackEndpointPolicy().validate("http://127.0.0.1:8105"))
    client.generate_response = lambda prompt: LocalModelResponse(text=answer, provider_id=client.provider_id,
        model_id=client.model_name, endpoint_class=client.endpoint.endpoint_class, usage={}, finish_reason="stop")
    runtime = LocalAgentRuntime(client)
    manifest, sources, _ = runtime.preview(question="Review fictional records", sources=(SOURCE,), run_id="fictional-run", created_at="2026-08-30T00:00:00Z")
    return runtime.run(LocalAgentRunRequest(question="Review fictional records", sources=sources,
        approved_manifest_sha256=manifest.manifest_sha256, run_id=manifest.run_id, manifest_created_at=manifest.created_at))


def test_real_runtime_returns_safe_withholding_and_audit_bound_result():
    result = run_answer('"Fictional title" [1]. Review required.')
    assert result.status == "specialist_output_blocked_review_required"
    assert '"Fictional title"' not in result.answer
    assert result.output_validation["status"] == "withheld"
    assert result.provenance_receipt.status == result.status
    assert result.to_dict()["output_validation"]["review_required"]


def test_runtime_accepts_bound_quote_without_certifying_claims():
    result = run_answer('"Only the March attachments subfolder was searched." [1]. Review required.')
    assert result.status == "completed_review_required"
    assert not result.blockers
    assert result.output_validation["factual_claims_verified"] is False
    assert result.output_validation["display_mode"] == "verified_extracts_only"


def test_valid_quote_does_not_launder_an_unsupported_narrative():
    result = run_answer('"Only the March attachments subfolder was searched." [1]. The full record is missing. Review required.')
    assert "The full record is missing" not in result.answer
    assert '"Only the March attachments subfolder was searched." [1]' in result.answer
    assert "other narrative was withheld" in result.answer
    assert "evidence_review_unverified_narrative_withheld" in result.warnings


def test_extract_renderer_rechecks_source_identity():
    from legal.fast_interchange.evidence_output import render_verified_evidence_extracts
    report = verify_evidence_output('"Only the March attachments subfolder was searched." [1]', (SOURCE,))
    with pytest.raises(ValueError, match="source_changed"):
        render_verified_evidence_extracts(report, (replace(SOURCE, text="Changed record"),))


def test_verifier_exception_fails_closed(monkeypatch):
    def broken(*args):
        raise RuntimeError("private internal detail")
    monkeypatch.setattr("legal.fast_interchange.evidence_output.verify_evidence_output", broken)
    result = run_answer('"Only the March attachments subfolder was searched." [1]')
    assert result.status == "specialist_output_blocked_review_required"
    assert "evidence_review_verifier_failed" in result.blockers
    assert "private internal detail" not in str(result.to_dict())


def test_production_ui_shows_source_check_limitations_and_mirrors_match():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    production = root / "src/maine_family_law_llm/ui/workbench.js"
    mirror = root / "maine_family_law_llm/ui/workbench.js"
    assert production.read_bytes() == mirror.read_bytes()
    text = production.read_text(encoding="utf-8")
    assert "Record quotations checked — review required" in text
    assert "Evidence Review withheld — review required" in text
    assert "This does not verify factual claims or establish what happened." in text
    assert "escapeHtml(code)" in text
    assert "escapeHtml(span.start_offset)" in text
    assert "Array.isArray(payload.blockers) ? payload.blockers : []" in text


def test_status_on_missing_authority_store_does_not_create_directories(tmp_path, monkeypatch):
    from app.services.authority_library_service import AuthorityLibraryService
    # Both are disposable siblings: authority remains outside the test repo.
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    missing = tmp_path / "missing-authority"
    report = AuthorityLibraryService(data_root=missing, repo_root=project).status()
    assert report["status"] == "blocked"
    assert not missing.exists()
