"""Unregistered research bridge from resident ranking to approved-source review.

This does not select a verified fact, infer absence, write a draft or grant
production admission. The canonical host must enforce authentication, source
capabilities, approval and encrypted audit before invoking the bridge.
"""

from dataclasses import dataclass, replace
from hashlib import sha256
from threading import Event, Lock

from legal.agent_runtime import ContextSource, LoopbackEndpointPolicy
from legal.agent_runtime.providers import (
    LocalModelResponse,
    SourceBoundGenerationClient,
    SourceRankingResponse,
)

from .compact_cpu import MAX_RESIDENT_BYTES, fail
from .compact_extracts import CompactExtractSelector, ExtractPlan, digest, source_state
from .compact_ranker_process import IsolatedCompactRanker, verify_ranks
from .compact_source_imports import SOURCE_IMPORT_VERSION
from .evidence_output import render_verified_evidence_extracts
from .ranked_evidence_output import verify_ranked_evidence_spans

POLICY = "up_to_three_candidates_per_record_no_abstention_or_truth_claim_v1"


@dataclass(frozen=True)
class RankedReviewPlan:
    extract: ExtractPlan
    approval_sha256: str

    def preview(self):
        result = self.extract.preview()
        result.update(
            task="research_record_passage_ranking",
            approval_sha256=self.approval_sha256,
            selection_policy=POLICY,
            coverage="Up to three candidate passages per record; relevance is not verified.",
            absence_verified=False,
            abstention_calibrated=False,
        )
        return result


class CompactRankedReview:
    def __init__(self, worker: IsolatedCompactRanker, *, research_only: bool):
        if research_only is not True:
            fail("compact_production_admission_missing")
        self.worker = worker
        self._prepare = CompactExtractSelector(None, research_only=True)
        self._cancel = Event()
        self._operation = Lock()
        self._inventory_sha256 = digest(
            [
                {"name": row.path.name, "sha256": row.sha256, "bytes": row.bytes}
                for row in worker.files
            ]
        )

    def _approval(self, plan):
        return digest(
            {"plan": plan.approval_sha256, "policy": POLICY, "inventory": self._inventory_sha256}
        )

    def prepare(self, *, question, sources, matter_id):
        plan = self._prepare.prepare(question=question, sources=sources, matter_id=matter_id)
        return RankedReviewPlan(plan, self._approval(plan))

    def run(self, plan, *, approved_sha256, sources, matter_id):
        if not isinstance(plan, RankedReviewPlan) or not isinstance(plan.extract, ExtractPlan):
            fail("compact_extract_approval_mismatch")
        base = plan.extract
        if not self._operation.acquire(blocking=False):
            fail("compact_extract_busy")
        if not base._lock.acquire(blocking=False):
            self._operation.release()
            fail("compact_extract_busy")
        try:
            if base._used:
                fail("compact_extract_approval_consumed")
            fresh = self._prepare.prepare(
                question=base.question, sources=sources, matter_id=matter_id, _run_id=base.run_id
            )
            expected = self._approval(fresh)
            if approved_sha256 != expected or plan.approval_sha256 != expected or fresh != base:
                fail("compact_extract_approval_mismatch")
            self._cancel.clear()
            base._used.append(True)
            spans, rankings = [], []
            for reference, source in enumerate(sources, 1):
                if self._cancel.is_set():
                    fail("generation_canceled")
                if digest(source_state(sources, matter_id)) != base.source_state_sha256:
                    fail("compact_extract_source_changed")
                candidates = [row for row in base.candidates if row.reference == reference]
                passages = [
                    {
                        "source_id": f"candidate-{row.candidate_id}",
                        "matter_id": matter_id,
                        "lane": "private_record",
                        "text": row.text,
                        "metadata": {"matter_id": matter_id},
                    }
                    for row in candidates
                ]
                # Original privacy metadata is already bound to this plan. Never
                # apply its full-record offsets to a newly sliced string.
                rows = self.worker.rank(
                    query=base.question,
                    passages=passages,
                    matter_id=matter_id,
                    cancellation=self._cancel,
                )
                rows = verify_ranks(rows, {"passages": passages})
                rankings.append({"reference": reference, "ranks": rows})
                for row in rows[:3]:
                    candidate = candidates[row["source_index"]]
                    spans.append(
                        {
                            "source_id": source.source_id,
                            "reference": reference,
                            "start_offset": candidate.start,
                            "end_offset": candidate.end,
                            "source_text_sha256": sha256(source.text.encode()).hexdigest(),
                            "quote_sha256": sha256(candidate.text.encode()).hexdigest(),
                            "status": "exact",
                        }
                    )
            if self._cancel.is_set():
                fail("generation_canceled")
            if digest(source_state(sources, matter_id)) != base.source_state_sha256:
                fail("compact_extract_source_changed")
            report = verify_ranked_evidence_spans(tuple(spans), sources)
            if report["blockers"]:
                fail("compact_extract_selection_invalid")
            report.update(
                approval_sha256=plan.approval_sha256,
                run_id=base.run_id,
                source_state_sha256=base.source_state_sha256,
                production_admitted=False,
                complete_draft=False,
                selection_policy=POLICY,
                rankings=rankings,
            )
            report["answer"] = render_verified_evidence_extracts(report, sources)
            report.pop("report_sha256", None)
            report["report_sha256"] = digest(report)
            return report
        finally:
            base._lock.release()
            self._operation.release()

    def cancel(self):
        self._cancel.set()
        self.worker.cancel()


class CompactRankedResearchClient(SourceBoundGenerationClient):
    """Only explicit research injection can select this client; no factory hook."""

    provider_id = "fast_interchange_local"
    model_name = "compact-research-record-passage-ranking"
    # Fixed non-serving descriptor for legacy provider metadata, never contacted.
    endpoint = LoopbackEndpointPolicy().validate("http://127.0.0.1:1")

    def __init__(self, worker: IsolatedCompactRanker, *, research_only: bool):
        self.review = CompactRankedReview(worker, research_only=research_only)
        self.worker = worker
        self.model_binding = {
            "capability": "evidence_review",
            "scope": "development",
            "runtime_abi": "compact_ranker_research_v1",
            "source_import_policy": SOURCE_IMPORT_VERSION,
            # These are the actual isolated worker limits, not a PEFT grant.
            # Factory/admission remain research-only; normal host hardware
            # checks can now run without a replacement assessor in tests.
            "compatibility": {
                "runtime_abi": "compact_ranker_research_v1",
                "quantization": "fp32",
                "execution_device": "cpu",
                "max_resident_bytes": MAX_RESIDENT_BYTES,
            },
            "output_mode": "record_passage_ranking",
            "selection_policy": POLICY,
            "transport": "private_anonymous_pipes",
            "production_admitted": False,
            "trained_specialist_adapter": False,
            "full_evidence_review_accepted": False,
            "complete_draft": False,
            "model_sha256": next(
                row.sha256 for row in worker.files if row.path.name == "model.safetensors"
            ),
            "review_required": True,
        }

    def generate_response(self, prompt):
        fail("compact_approved_source_objects_required")

    def generate_bound_response(self, prompt, *, question, sources, matter_id):
        if (
            not isinstance(matter_id, str)
            or not matter_id
            or not isinstance(sources, tuple)
            or any(
                not isinstance(row, ContextSource)
                or not isinstance(row.metadata, dict)
                or row.metadata.get("matter_id", matter_id) != matter_id
                for row in sources
            )
        ):
            fail("compact_extract_scope_invalid")
        # The canonical host may attach its already-checked scope, never replace
        # an existing different matter. No prompt/XML parsing is used.
        bound = tuple(replace(s, metadata={**s.metadata, "matter_id": matter_id}) for s in sources)
        plan = self.review.prepare(question=question, sources=bound, matter_id=matter_id)
        report = self.review.run(
            plan, approved_sha256=plan.approval_sha256, sources=bound, matter_id=matter_id
        )
        refs = ", ".join(f"[{i}]" for i in range(1, len(bound) + 1))
        return SourceRankingResponse(
            text=f"Candidate passages to inspect: {refs}. Relevance unverified. Review required.",
            provider_id=self.provider_id,
            model_id=self.model_name,
            endpoint_class=self.endpoint.endpoint_class,
            usage={},
            finish_reason="stop",
            source_spans=tuple(report["source_spans"]),
        )

    def warm(self):
        self.worker.warm()
        return LocalModelResponse(
            text="READY",
            provider_id=self.provider_id,
            model_id=self.model_name,
            endpoint_class=self.endpoint.endpoint_class,
            finish_reason="stop",
        )

    @property
    def supports_explicit_release(self):
        return True

    def cancel(self):
        self.review.cancel()

    def release(self):
        self.worker.close()
