"""Fictional fail-closed tests; these do not certify model quality."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from legal.agent_runtime import (
    ContextSource,
    LocalAgentRunRequest,
    LocalAgentRuntime,
    LocalModelResponse,
)
from legal.agent_runtime.providers import LoopbackEndpointPolicy
from legal.fast_interchange.drafting_output import render_source_bound_draft, verify_drafting_output

SOURCE = ContextSource(
    source_id="fictional-message",
    lane="private_record",
    title="Fictional message",
    locator="fictional page 2",
    text="The message proposes an exchange at 16:30 if transportation is confirmed.",
)


@pytest.mark.parametrize(
    "answer,source,blocker",
    [
        ("The exchange is at 16:30 [1].", SOURCE, "drafting_exact_quote_required"),
        ('"The exchange is at 17:30." [1]', SOURCE, "drafting_quote_not_in_cited_record"),
        (
            '"The message proposes an exchange at 16:30 if transportation is confirmed." [7]',
            SOURCE,
            "specialist_source_references_required",
        ),
        (
            '"The message proposes an exchange at 16:30 if transportation is confirmed." '
            "[1] Under 2099 ME 777 this is required.",
            SOURCE,
            "drafting_legal_authority_not_verified",
        ),
        (
            '"The message proposes an exchange at 16:30 if transportation is confirmed." [1]',
            replace(SOURCE, lane="legal_authority"),
            "drafting_private_record_sources_required",
        ),
    ],
)
def test_drafting_bad_output_is_withheld(answer, source, blocker):
    report = verify_drafting_output(answer, (source,))
    assert report["status"] == "withheld"
    assert blocker in report["blockers"]


def test_drafting_renderer_exposes_only_rechecked_source_text():
    raw = (
        'The exchange is final. "The message proposes an exchange at 16:30 if transportation '
        'is confirmed." [1] Everyone agreed. Review required.'
    )
    report = verify_drafting_output(raw, (SOURCE,))
    rendered = render_source_bound_draft(report, (SOURCE,))
    assert "The exchange is final" not in rendered
    assert "Everyone agreed" not in rendered
    assert (
        '"The message proposes an exchange at 16:30 if transportation is confirmed." [1]'
        in rendered
    )
    assert report["filing_ready"] is False
    assert report["factual_claims_verified"] is False


def test_drafting_model_cannot_hide_a_selected_conflicting_record():
    second = replace(
        SOURCE,
        source_id="fictional-second-record",
        text="A second record lists the exchange at 18:15.",
    )
    report = verify_drafting_output(
        '"The message proposes an exchange at 16:30 if transportation is confirmed." '
        "[1] Review required.",
        (SOURCE, second),
    )
    assert report["status"] == "withheld"
    assert "drafting_all_records_required" in report["blockers"]


def _run(answer: str):
    client = SimpleNamespace(
        provider_id="fast_interchange_local",
        model_name="fictional-drafting-model",
        model_binding={"capability": "drafting"},
        endpoint=LoopbackEndpointPolicy().validate("http://127.0.0.1:8105"),
    )
    client.generate_response = lambda prompt: LocalModelResponse(
        text=answer,
        provider_id=client.provider_id,
        model_id=client.model_name,
        endpoint_class=client.endpoint.endpoint_class,
        usage={},
        finish_reason="stop",
    )
    runtime = LocalAgentRuntime(client)
    manifest, sources, _ = runtime.preview(
        question="Prepare a fictional working extract",
        sources=(SOURCE,),
        run_id="fictional-drafting-run",
        created_at="2026-09-01T00:00:00Z",
    )
    return runtime.run(
        LocalAgentRunRequest(
            question="Prepare a fictional working extract",
            sources=sources,
            approved_manifest_sha256=manifest.manifest_sha256,
            run_id=manifest.run_id,
            manifest_created_at=manifest.created_at,
        )
    )


def test_runtime_returns_source_bound_working_material():
    result = _run(
        'This is agreed. "The message proposes an exchange at 16:30 if transportation is '
        'confirmed." [1] Review required.'
    )
    assert result.status == "completed_review_required"
    assert "This is agreed" not in result.answer
    assert "source-bound working material" in result.answer
    assert result.output_validation["display_mode"] == "source_bound_draft_extracts_only"
    assert result.output_validation["filing_ready"] is False
    assert "drafting_unverified_narrative_withheld" in result.warnings


def test_sensitive_value_is_withheld_but_safe_excerpt_survives():
    source = replace(
        SOURCE,
        text=(
            "Private identifier: FICTIONAL-7788. "
            "The note reports a request to reschedule the meeting."
        ),
    )
    raw = (
        '"The note reports a request to reschedule the meeting." [1] '
        '"Private identifier: FICTIONAL-7788." [1] Review required.'
    )
    report = verify_drafting_output(raw, (source,))
    rendered = render_source_bound_draft(report, (source,), allow_partial=True)
    assert report["status"] == "partial_quoted_spans_bound_review_required"
    assert "FICTIONAL-7788" not in rendered
    assert "request to reschedule" in rendered


def test_drafting_verifier_exception_fails_closed(monkeypatch):
    def broken(*args):
        raise RuntimeError("private internal detail")

    monkeypatch.setattr("legal.fast_interchange.drafting_output.verify_drafting_output", broken)
    result = _run('"The message proposes an exchange at 16:30 if transportation is confirmed." [1]')
    assert result.status == "specialist_output_blocked_review_required"
    assert "drafting_verifier_failed" in result.blockers
    assert "private internal detail" not in str(result.to_dict())
