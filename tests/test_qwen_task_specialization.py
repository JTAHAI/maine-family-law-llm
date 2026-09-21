"""Regression coverage for the bounded Qwen Evidence/Drafting task profiles."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from legal.agent_runtime import ContextSource, LocalAgentRunRequest, LocalAgentRuntime
from legal.agent_runtime.providers import CuratedOllamaReasoningClient, LocalModelError
from legal.agent_runtime.qwen_review import verify_qwen_excerpts
from legal.agent_runtime.task_profiles import task_profile
from legal.fast_interchange.authority_output import render_verified_authority_extracts
from app.services.local_agent_context_service import LocalAgentContextService
from legal.fast_interchange.drafting_output import render_source_bound_draft
from legal.fast_interchange.evidence_output import render_verified_evidence_extracts


def source(text: str, source_id: str = "fictional-record") -> ContextSource:
    return ContextSource(
        source_id=source_id,
        lane="private_record",
        title="Fictional record",
        text=text,
        locator="fictional page 1",
    )


def authority_source(text: str, source_id: str = "fictional-maine-authority") -> ContextSource:
    return ContextSource(
        source_id=source_id,
        lane="legal_authority",
        title="Fictional official Maine authority",
        text=text,
        locator="fictional section 1",
        source_class="court_rule",
        authority_status="verified_immutable_source_not_current_law_determination",
        freshness_status="fresh",
        metadata={
            "jurisdiction": "maine",
            "official_source_url": "https://www.courts.maine.gov/fictional-rule",
            "authority_build_id": "fictional-immutable-build",
        },
    )


def test_task_profile_is_hash_bound_and_not_an_admission():
    profile = task_profile(task="evidence_review", model_name="qwen3:4b")
    assert profile["output_mode"] == "selected_spans_with_review_flags"
    assert profile["production_admitted"] is False
    assert profile["quality_status"] == "local_runtime_only_not_legal_qualified"
    assert profile["max_output_tokens"] == 768
    assert profile["profile_revision"] == "qwen-task-profile-v2"
    assert len(profile["profile_sha256"]) == 64
    assert profile == task_profile(task="evidence_review", model_name="qwen3:4b")
    with pytest.raises(ValueError):
        task_profile(task="invented", model_name="qwen3:4b")


def test_curated_qwen_does_not_present_unimplemented_task_names_as_specialists():
    with pytest.raises(LocalModelError, match="Evidence Review"):
        CuratedOllamaReasoningClient(capability="parenting_plan_review")


def test_authority_profile_is_exact_source_selection_not_legal_model_admission():
    profile = task_profile(task="authority_review", model_name="qwen3:8b")
    assert profile["output_mode"] == "selected_official_authority_spans"
    assert profile["production_admitted"] is False


@pytest.mark.parametrize(
    "url",
    [
        "http://www.courts.maine.gov/fictional-rule",
        "https://www.courts.maine.gov@evil.example/fictional-rule",
        "https://evil.example/fictional-rule",
        "https://www.courts.maine.gov:444/fictional-rule",
    ],
)
def test_authority_review_rejects_unadmitted_or_unsafe_provenance_urls(url):
    from legal.fast_interchange.authority_output import verify_selected_authority_spans

    record = replace(
        authority_source("A fictional rule sentence."),
        metadata={
            "jurisdiction": "maine",
            "official_source_url": url,
        },
    )
    report = verify_selected_authority_spans((), (record,))
    assert report["status"] == "withheld"
    assert "authority_review_official_fresh_maine_sources_required" in report["blockers"]


def test_authority_context_does_not_send_nonofficial_url_to_local_model(monkeypatch):
    class FakeAuthority:
        def _active_product(self, verify_all):
            assert verify_all is True
            return SimpleNamespace(build_id="fictional-build", manifest_path="unused")

        def _sha256_file(self, _path):
            return "a" * 64

        def _iter_active_parsed_rows(self, _active):
            return iter(
                [
                    {
                        "record_id": "fictional-source",
                        "text": "Fictional official-looking text.",
                        "source_hash": "b" * 64,
                    }
                ]
            )

        def authority_lineage(self, _source_id):
            return {
                "status": "lineage_observed",
                "official_source": {"admitted": True, "url": "https://evil.example/"},
                "parsed_node": {"jurisdiction": "maine", "parser_status": "parsed"},
                "retrieval_event": {},
                "snapshot": {},
            }

    service = LocalAgentContextService(record_loader=lambda _token: {}, authority=FakeAuthority())
    assert service._authority_rows({"fictional-source"}) == {}


def test_short_fragment_renders_original_sentence_with_negation_context():
    record = source("The receipt was requested, but no receipt was supplied.")
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "receipt was supplied"}], (record,)
    )
    assert report["blockers"] == []
    span = report["source_spans"][0]
    assert record.text[span["start_offset"] : span["end_offset"]] == record.text
    rendered = render_verified_evidence_extracts(report, (record,))
    assert "no receipt was supplied" in rendered
    assert report["factual_claims_verified"] is False


def test_multiple_distinct_passages_from_one_record_are_allowed_and_deduplicated():
    record = source("First statement is fictional. Second qualification is fictional.")
    report = verify_qwen_excerpts(
        [
            {"reference": 1, "quote": "First statement is fictional."},
            {"reference": 1, "quote": "Second qualification is fictional."},
        ],
        (record,),
        review_flags=(
            {"kind": "qualification", "references": [1]},
        ),
    )
    assert report["blockers"] == []
    assert len(report["source_spans"]) == 2
    rendered = render_verified_evidence_extracts(report, (record,))
    assert "Model review cues — not findings" in rendered
    assert "qualification or limitation" in rendered.casefold()


def test_evidence_review_can_expose_a_complete_nonexcerpt_coverage_inventory():
    selected = source("The fictional receipt says the payment was requested.", "record-selected")
    unselected = source("The fictional calendar describes a different event.", "record-unselected")
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "receipt says the payment was requested."}],
        (selected, unselected),
        coverage=(
            {"reference": 1, "state": "selected_excerpt"},
            {"reference": 2, "state": "not_relevant"},
        ),
    )
    assert report["blockers"] == []
    assert report["coverage_complete"] is True
    assert report["coverage"][1] == {"reference": 2, "state": "not_relevant"}
    rendered = render_verified_evidence_extracts(report, (selected, unselected))
    assert "model suggestions, not completeness proof" in rendered
    assert "does not establish that information is absent or irrelevant" in rendered


def test_evidence_review_rejects_incomplete_or_mismatched_coverage_inventory():
    first = source("First fictional record has a checked sentence.", "record-first")
    second = source("Second fictional record is different.", "record-second")
    missing = verify_qwen_excerpts(
        [{"reference": 1, "quote": "fictional record has a checked sentence."}],
        (first, second),
        coverage=({"reference": 1, "state": "selected_excerpt"},),
    )
    assert "evidence_review_coverage_incomplete" in missing["blockers"]
    mismatch = verify_qwen_excerpts(
        [{"reference": 1, "quote": "fictional record has a checked sentence."}],
        (first, second),
        coverage=(
            {"reference": 1, "state": "not_relevant"},
            {"reference": 2, "state": "unprocessed"},
        ),
    )
    assert "evidence_review_coverage_selected_excerpt_required" in mismatch["blockers"]


def test_ambiguous_model_quote_is_withheld_instead_of_selecting_first_occurrence():
    record = source("Repeated detail. Different middle. Repeated detail.")
    with pytest.raises(ValueError, match="quote_ambiguous_in_record"):
        verify_qwen_excerpts([{"reference": 1, "quote": "Repeated detail."}], (record,))


def test_drafting_uses_same_bound_cues_without_turning_them_into_findings():
    record = source("A fictional proposal was sent. No acceptance is recorded.")
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "No acceptance is recorded."}],
        (record,),
        task="drafting",
        review_flags=({"kind": "proposal_not_acceptance", "references": [1]},),
        draft_sections=({"heading": "record_difference", "references": [1]},),
    )
    rendered = render_source_bound_draft(report, (record,))
    assert "Working outline — model-organized review material, not findings" in rendered
    assert "Record differences to review" in rendered
    assert "Working-outline review cues — not findings" in rendered
    assert "Proposal/acceptance wording to review" in rendered
    assert "filing-ready draft" in rendered


def test_prompt_budget_includes_the_structured_output_contract():
    client = CuratedOllamaReasoningClient(capability="evidence_review")
    runtime = LocalAgentRuntime(client)
    record = source("Fictional short source.")
    budget = runtime.context_budget(question="Review the fictional source", sources=(record,))
    assert budget["status"] == "ready_for_approval"
    assert budget["used_bytes"] < budget["maximum_bytes"]
    oversized = runtime.context_budget(question="é" * 3000, sources=(record,))
    assert oversized["status"] == "context_too_large"
    assert oversized["within_budget"] is False


def test_provider_rejects_late_cancel_and_accepts_only_bound_flags(monkeypatch):
    client = CuratedOllamaReasoningClient(capability="evidence_review")

    def post(_path, _body):
        return {
            "model": "qwen3:4b",
            "done": True,
            "done_reason": "stop",
            "response": json.dumps(
                {
                    "excerpts": [{"reference": 1, "quote": "Fictional source."}],
                    "review_flags": [{"kind": "possible_conflict", "references": [1]}],
                    "coverage": [{"reference": 1, "state": "selected_excerpt"}],
                }
            ),
        }

    monkeypatch.setattr(client._http, "post_json", post)
    response = client.generate_response("Fictional source.")
    assert response.review_flags[0]["kind"] == "possible_conflict"
    assert response.coverage == ({"reference": 1, "state": "selected_excerpt"},)
    client.cancel()
    with pytest.raises(LocalModelError, match="Generation canceled"):
        client.generate_response("Fictional source.")


def test_qwen_8b_timeout_fails_closed_with_a_smaller_model_recovery_path(monkeypatch):
    client = CuratedOllamaReasoningClient(model_name="qwen3:8b", capability="evidence_review")

    def timeout(_path, _body):
        raise LocalModelError("local_model_timeout", "fictional timeout")

    monkeypatch.setattr(client._http, "post_json", timeout)
    runtime = LocalAgentRuntime(client)
    record = source("A fictional record is available for review.")
    manifest, _, _ = runtime.preview(
        question="Review the fictional record.", sources=(record,), run_id="qwen-8b-timeout"
    )
    result = runtime.run(
        LocalAgentRunRequest(
            question="Review the fictional record.",
            sources=(record,),
            approved_manifest_sha256=manifest.manifest_sha256,
            matter_id="fictional-matter",
            run_id="qwen-8b-timeout",
            manifest_created_at=manifest.created_at,
        )
    )
    assert result.status == "local_model_failed_review_required"
    assert "No model answer was accepted" in result.answer
    assert "4B option" in result.answer
    assert "switch models automatically" in result.answer


def test_drafting_provider_accepts_only_fixed_sections_and_evidence_rejects_them(monkeypatch):
    def post(_path, _body):
        return {
            "model": "qwen3:4b",
            "done": True,
            "done_reason": "stop",
            "response": json.dumps(
                {
                    "excerpts": [{"reference": 1, "quote": "Fictional source."}],
                    "draft_sections": [
                        {"heading": "background", "references": [1]},
                    ],
                }
            ),
        }

    drafting = CuratedOllamaReasoningClient(capability="drafting")
    monkeypatch.setattr(drafting._http, "post_json", post)
    response = drafting.generate_response("Fictional source.")
    assert response.draft_sections == ({"heading": "background", "references": [1]},)

    evidence = CuratedOllamaReasoningClient(capability="evidence_review")
    monkeypatch.setattr(evidence._http, "post_json", post)
    with pytest.raises(LocalModelError, match="verifiable excerpts"):
        evidence.generate_response("Fictional source.")


def test_drafting_sections_must_reference_a_verified_extract():
    record = source("A fictional record says a response was mailed.")
    with pytest.raises(ValueError, match="draft_section_unbound"):
        verify_qwen_excerpts(
            [{"reference": 1, "quote": "response was mailed."}],
            (record,),
            task="drafting",
            draft_sections=({"heading": "background", "references": [2]},),
        )


def test_authority_review_renders_only_fresh_host_verified_official_passages():
    authority = authority_source("Fictional official Maine rule text requires an exact source review.")
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "official Maine rule text requires an exact source review."}],
        (authority,),
        task="authority_review",
    )
    assert report["blockers"] == []
    rendered = render_verified_authority_extracts(report, (authority,))
    assert "Maine Authority Review" in rendered
    assert "do not determine current law" in rendered
    assert "Fictional official Maine rule text" in rendered


def test_authority_review_fails_closed_on_stale_or_non_official_sources():
    authority = authority_source("Fictional authority text.")
    stale = ContextSource(
        **{**authority.__dict__, "freshness_status": "stale"}
    )
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "Fictional authority text."}],
        (stale,),
        task="authority_review",
    )
    assert "authority_review_official_fresh_maine_sources_required" in report["blockers"]


def test_authority_review_requires_public_maine_provenance_not_only_a_status_label():
    authority = authority_source("Fictional authority text.")
    untraceable = ContextSource(**{**authority.__dict__, "metadata": {}})
    report = verify_qwen_excerpts(
        [{"reference": 1, "quote": "Fictional authority text."}],
        (untraceable,),
        task="authority_review",
    )
    assert "authority_review_official_fresh_maine_sources_required" in report["blockers"]


def test_authority_review_runs_through_the_local_runtime_with_exact_official_text(monkeypatch):
    authority = authority_source("Fictional official Maine rule requires a checked source.")
    client = CuratedOllamaReasoningClient(capability="authority_review")

    def post(_path, _body):
        return {
            "model": "qwen3:4b",
            "done": True,
            "done_reason": "stop",
            "response": json.dumps(
                {
                    "excerpts": [
                        {"reference": 1, "quote": "official Maine rule requires a checked source."}
                    ]
                }
            ),
        }

    monkeypatch.setattr(client._http, "post_json", post)
    runtime = LocalAgentRuntime(client)
    manifest, _, _ = runtime.preview(
        question="Review this fictional official source.", sources=(authority,), run_id="authority-qwen-test"
    )
    result = runtime.run(
        LocalAgentRunRequest(
            question="Review this fictional official source.",
            sources=(authority,),
                approved_manifest_sha256=manifest.manifest_sha256,
                matter_id="fictional-matter",
                run_id="authority-qwen-test",
                manifest_created_at=manifest.created_at,
        )
    )
    assert result.status == "completed_review_required", result.blockers
    assert "Maine Authority Review" in result.answer
    assert result.output_validation["schema_version"] == "authority_selected_spans_boundary_v1"
    assert result.model["admission"]["production_admitted"] is False
