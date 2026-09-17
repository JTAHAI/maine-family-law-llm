"""Fictional host-boundary tests; fake scores do not measure model quality."""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal.agent_runtime import ContextSource, LocalAgentRunRequest, LocalAgentRuntime
from legal.agent_runtime.providers import LocalModelError, SourceRankingResponse
from legal.fast_interchange.compact_ranked_review import (
    CompactRankedResearchClient,
    CompactRankedReview,
)
from legal.fast_interchange.evidence_output import (
    render_verified_evidence_extracts,
    verify_selected_evidence_spans,
)
from legal.fast_interchange.ranked_evidence_output import verify_ranked_evidence_spans

MATTER = "fictional-ranking-matter"


class FakeRanker:
    files = (SimpleNamespace(path=Path("model.safetensors"), sha256="a" * 64, bytes=42),)

    def __init__(self):
        self.calls, self.hook, self.transform = [], None, None
        self.canceled = self.closed = False

    def rank(self, *, query, passages, matter_id, cancellation=None):
        self.calls.append({"query": query, "passages": passages, "matter_id": matter_id})
        if self.hook:
            self.hook()
        rows = [
            {
                "source_id": row["source_id"],
                "source_index": i,
                "source_sha256": sha256(row["text"].encode()).hexdigest(),
                "relevance_score": -float(i),
                "score_meaning": "passage_relevance_only",
                "review_required": True,
                "truth_verified": False,
            }
            for i, row in enumerate(passages)
        ]
        return self.transform(rows) if self.transform else rows

    def warm(self):
        return {"status": "warm"}

    def cancel(self):
        self.canceled = True

    def close(self):
        self.closed = True


def records():
    return (
        ContextSource(
            "fictional-a",
            "private_record",
            "Title must not be ranked",
            'A letter says "copy missing". A later message says a copy was sent. '
            "Receipt is not shown. The paper is blue. The envelope is blank.",
            metadata={"matter_id": MATTER},
        ),
        ContextSource(
            "fictional-b",
            "private_record",
            "Other title",
            "The register lists an entry date. Delivery is not documented.",
            metadata={"matter_id": MATTER},
        ),
    )


def setup():
    worker = FakeRanker()
    service = CompactRankedReview(worker, research_only=True)
    sources = records()
    plan = service.prepare(
        question="Find the missing copy and delivery record.", sources=sources, matter_id=MATTER
    )
    return worker, service, sources, plan


def execute(service, sources, plan):
    return service.run(
        plan, approved_sha256=plan.approval_sha256, sources=sources, matter_id=MATTER
    )


def test_shortlist_preserves_literal_sources_and_never_asserts_relevance_or_absence():
    worker, service, sources, plan = setup()
    report = execute(service, sources, plan)
    assert len(report["source_spans"]) == 5  # three from first, both from second
    assert len(worker.calls) == 2
    assert '"copy missing"' in report["answer"]
    assert "relevance is unknown" in report["answer"]
    assert "even when none answers the question" in report["answer"]
    assert "not an answer or finding" in report["answer"]
    assert "other narrative" not in report["answer"]
    assert "Title must not" not in json.dumps(worker.calls)
    for flag in (
        "production_admitted",
        "factual_claims_verified",
        "legal_claims_verified",
        "relevance_verified",
        "complete_draft",
        "abstention_calibrated",
    ):
        assert report[flag] is False
    assert report["review_required"] is True
    assert "Up to three" in plan.preview()["coverage"]
    with pytest.raises(LocalModelError) as error:
        execute(service, sources, plan)
    assert error.value.code.endswith("approval_consumed")


@pytest.mark.parametrize("change", ["text", "privacy", "scope", "id", "approval", "span", "model"])
def test_stale_and_cross_model_approval_fails_before_inference(change):
    worker, service, sources, plan = setup()
    if change == "text":
        sources = (replace(sources[0], text="Changed body."), sources[1])
    elif change == "privacy":
        sources[0].metadata["exclude_from_model"] = True
    elif change == "scope":
        sources[0].metadata["matter_id"] = "other"
    elif change == "id":
        sources = (replace(sources[0], source_id="changed-id"), sources[1])
    elif change == "approval":
        plan = replace(plan, approval_sha256="b" * 64)
    elif change == "span":
        candidate = replace(plan.extract.candidates[0], start=1)
        plan = replace(
            plan,
            extract=replace(plan.extract, candidates=(candidate, *plan.extract.candidates[1:])),
        )
    elif change == "model":
        other = FakeRanker()
        other.files = (SimpleNamespace(path=Path("model.safetensors"), sha256="b" * 64, bytes=42),)
        service = CompactRankedReview(other, research_only=True)
    with pytest.raises(LocalModelError):
        execute(service, sources, plan)
    assert not worker.calls


@pytest.mark.parametrize("change", ["text", "privacy", "cancel", "busy"])
def test_changes_and_cancel_between_record_rankings_prevent_partial_return(change):
    worker, service, sources, plan = setup()

    def hook():
        if change == "text":
            object.__setattr__(sources[1], "text", "Changed after dispatch.")
        elif change == "privacy":
            sources[1].metadata["exclude_from_model"] = True
        elif change == "cancel":
            service.cancel()
        else:
            other = service.prepare(question="Another question", sources=sources, matter_id=MATTER)
            with pytest.raises(LocalModelError) as error:
                execute(service, sources, other)
            assert error.value.code.endswith("busy")
            service.cancel()

    worker.hook = hook
    with pytest.raises(LocalModelError):
        execute(service, sources, plan)
    assert len(worker.calls) == 1
    assert plan.extract._used


@pytest.mark.parametrize(
    "field,value",
    [
        ("truth_verified", True),
        ("review_required", False),
        ("source_index", True),
        ("source_index", 999),
        ("source_sha256", "a" * 64),
        ("source_id", "other"),
        ("relevance_score", float("nan")),
        ("invented_prose", "not allowed"),
    ],
)
def test_forged_worker_rank_cannot_bypass_host_checks(field, value):
    worker, service, sources, plan = setup()
    worker.transform = lambda rows: [{**rows[0], field: value}, *rows[1:]]
    with pytest.raises(LocalModelError):
        execute(service, sources, plan)


def test_sensitive_sentence_is_not_sent_and_record_offset_metadata_is_not_rebased():
    worker = FakeRanker()
    service = CompactRankedReview(worker, research_only=True)
    text = "Account: fictional-secret-777. The message lacks the copy."
    source = ContextSource(
        "fictional-private", "private_record", "Fictional", text, metadata={"matter_id": MATTER}
    )
    plan = service.prepare(question="Find the copy", sources=(source,), matter_id=MATTER)
    result = execute(service, (source,), plan)
    assert "fictional-secret" not in json.dumps(worker.calls)
    assert "fictional-secret" not in result["answer"]
    assert result["source_spans"][0]["start_offset"] > 0


@pytest.mark.parametrize(
    "changed",
    [
        "missing",
        "duplicate",
        "overlap",
        "too_many",
        "unknown_key",
        "wrong_hash",
        "string_offset",
        "privacy",
        "wrong_lane",
    ],
)
def test_independent_ranked_verifier_never_relaxes_existing_exact_boundary(changed):
    _, service, sources, plan = setup()
    result = execute(service, sources, plan)
    spans = tuple(result["source_spans"])
    assert not verify_ranked_evidence_spans(spans, sources)["blockers"]
    assert verify_selected_evidence_spans(spans, sources)["blockers"]  # old mode remains strict
    if changed == "missing":
        spans = tuple(row for row in spans if row["reference"] == 1)
    elif changed == "duplicate":
        spans = (*spans[:1], spans[0], *spans[2:])
    elif changed == "overlap":
        row = spans[0]
        quote = sources[0].text[1 : row["end_offset"]]
        spans = (
            row,
            {**row, "start_offset": 1, "quote_sha256": sha256(quote.encode()).hexdigest()},
            *spans[2:],
        )
    elif changed == "too_many":
        spans = (*spans, spans[0])
    elif changed == "unknown_key":
        spans = ({**spans[0], "text": "invented"}, *spans[1:])
    elif changed == "wrong_hash":
        spans = ({**spans[0], "quote_sha256": "c" * 64}, *spans[1:])
    elif changed == "string_offset":
        spans = ({**spans[0], "start_offset": "0"}, *spans[1:])
    elif changed == "privacy":
        sources[0].metadata["exclude_from_model"] = True
    elif changed == "wrong_lane":
        sources = (replace(sources[0], lane="legal_authority"), sources[1])
    checked = verify_ranked_evidence_spans(spans, sources)
    assert checked["blockers"] and not checked["source_spans"]
    with pytest.raises(ValueError):
        render_verified_evidence_extracts(checked, sources)


def host_run(client):
    runtime = LocalAgentRuntime(client)
    sources = tuple(replace(source, metadata={}) for source in records())
    question = "Find the missing copy."
    manifest, selected, _ = runtime.preview(question=question, sources=sources)
    return runtime.run(
        LocalAgentRunRequest(
            question,
            selected,
            manifest.manifest_sha256,
            matter_id=MATTER,
            run_id=manifest.run_id,
            manifest_created_at=manifest.created_at,
        )
    )


def test_timeout_returns_safe_review_required_recovery_without_claiming_a_result():
    worker = FakeRanker()
    client = CompactRankedResearchClient(worker, research_only=True)

    def timeout(*args, **kwargs):
        raise LocalModelError("fast_interchange_generation_timeout", "private exception canary")

    client.generate_bound_response = timeout
    result = host_run(client)
    assert result.status == "local_model_failed_review_required"
    assert "fast_interchange_generation_timeout" in result.warnings
    assert "exceeded its time limit" in result.answer
    assert "inspect the selected sources without the model" in result.answer
    assert "Review required" in result.answer
    assert "private exception canary" not in result.answer
    assert not worker.calls


def test_host_renders_ranked_exact_spans_with_unique_source_cards_and_honest_warning():
    worker = FakeRanker()
    result = host_run(CompactRankedResearchClient(worker, research_only=True))
    assert result.status == "completed_review_required"
    assert len(result.output_validation["source_spans"]) == 5
    assert list(result.provenance_receipt.citation_refs) == [1, 2]
    assert "evidence_review_ranked_relevance_unknown" in result.warnings
    assert "evidence_review_unverified_narrative_withheld" not in result.warnings
    assert result.model["admission"]["production_admitted"] is False
    assert "not an answer or finding" in result.answer


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_id", "wrong-provider"),
        ("model_id", "wrong-model"),
        ("endpoint_class", "external"),
        ("finish_reason", "length"),
    ],
)
def test_host_rejects_wrong_response_identity(field, value):
    client = CompactRankedResearchClient(FakeRanker(), research_only=True)
    original = client.generate_bound_response
    client.generate_bound_response = lambda *args, **kwargs: replace(
        original(*args, **kwargs), **{field: value}
    )
    result = host_run(client)
    assert "source_selection_binding_invalid" in result.warnings
    assert not result.output_validation


def test_wrong_mode_and_unknown_response_subclass_fail_closed():
    client = CompactRankedResearchClient(FakeRanker(), research_only=True)
    client.model_binding["output_mode"] = "record_excerpt_selection"
    assert "source_selection_binding_invalid" in host_run(client).warnings

    class UnknownResponse(SourceRankingResponse):
        pass

    client.model_binding["output_mode"] = "unsupported"
    original = client.generate_bound_response
    client.generate_bound_response = lambda *args, **kwargs: UnknownResponse(
        **vars(original(*args, **kwargs))
    )
    assert "source_selection_binding_invalid" in host_run(client).warnings


def test_research_gate_warm_release_no_untyped_prompt_or_scope_relabel():
    worker = FakeRanker()
    with pytest.raises(LocalModelError):
        CompactRankedResearchClient(worker, research_only=False)
    client = CompactRankedResearchClient(worker, research_only=True)
    assert client.warm().text == "READY"
    assert not worker.calls
    with pytest.raises(LocalModelError):
        client.generate_response("Invented source markup")
    with pytest.raises(LocalModelError):
        client.generate_bound_response(
            "", question="Question", sources=records(), matter_id="other"
        )
    client.release()
    assert worker.closed


def test_source_bound_tools_block_before_broker_or_model_even_if_permitted():
    from legal.agent_runtime.tools import ToolInvocation

    worker = FakeRanker()
    runtime = LocalAgentRuntime(CompactRankedResearchClient(worker, research_only=True))
    runtime.tool_broker = SimpleNamespace(execute_many=lambda *a, **kw: pytest.fail("Tool ran"))
    question = "Find the copy."
    manifest, sources, _ = runtime.preview(question=question, sources=records())
    result = runtime.run(
        LocalAgentRunRequest(
            question,
            sources,
            manifest.manifest_sha256,
            matter_id=MATTER,
            run_id=manifest.run_id,
            manifest_created_at=manifest.created_at,
            tool_invocations=(ToolInvocation("record_search", {"q": "copy"}),),
            permitted_tools=frozenset({"record_search"}),
        )
    )
    assert result.status == "blocked"
    assert "source_bound_tools_unsupported" in result.blockers
    assert result.tool_receipts == ()
    assert not worker.calls


def test_exploratory_threshold_uses_calibration_only_and_does_not_call_scores_probabilities():
    from scripts.verify_compact_ranked_review import calibration_threshold, metrics

    calibration = [{"top_score": 2.0, "relevant": []}, {"top_score": 99.0, "relevant": [1]}]
    threshold = calibration_threshold(calibration)
    assert threshold > 2.0 and threshold < 2.001
    measured = metrics(
        [
            {"relevant": [], "top_score": 4.0},
            {
                "relevant": [1],
                "top_score": 1.0,
                "top1_relevant": True,
                "all_relevant_in_top3": True,
                "recall_at3": 1.0,
            },
        ],
        threshold,
    )
    assert measured["experimental_false_accepts"] == 1
    assert measured["experimental_positive_abstentions"] == 1
    assert measured["threshold_is_not_production_policy"] is True
    assert calibration_threshold(calibration) == threshold


@pytest.mark.parametrize(
    "rows",
    [[], [{"relevant": [], "top_score": float("nan")}], [{"relevant": [], "top_score": True}]],
)
def test_invalid_calibration_scores_fail_closed(rows):
    from scripts.verify_compact_ranked_review import calibration_threshold

    with pytest.raises(ValueError):
        calibration_threshold(rows)
