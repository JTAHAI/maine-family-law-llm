"""Explicit research injection only; never selected by the production factory.

Field/basis are fixed for the client's model identity, visible in the approved
binding and cannot be inferred from documents or silently changed after preview.
"""

from dataclasses import replace
from threading import Event, Lock

from legal.agent_runtime import ContextSource, LoopbackEndpointPolicy
from legal.agent_runtime.providers import (
    LocalModelResponse,
    SourceBoundGenerationClient,
    SourceFieldResponse,
)

from .compact_clause_review import POLICY
from .compact_cpu import MAX_RESIDENT_BYTES, fail
from .compact_extracts import digest, source_state
from .compact_field_output import field_passages, validate_contract, verify_field_output
from .compact_reranker import rank_input
from .compact_source_imports import SOURCE_IMPORT_VERSION
from .compact_span_process import SPAN_RUNTIME_ABI


class CompactFieldResearchClient(SourceBoundGenerationClient):
    provider_id = "fast_interchange_local"
    endpoint = LoopbackEndpointPolicy().validate("http://127.0.0.1:1")

    def __init__(self, worker, *, field_type, basis, research_only):
        if research_only is not True:
            fail("compact_production_admission_missing")
        validate_contract(field_type, basis)
        self.worker, self.field_type, self.basis = worker, field_type, basis
        self.model_name = f"compact-research-{field_type}-{basis}"
        self._cancel, self._operation = Event(), Lock()
        self.model_binding = dict(
            capability="evidence_review",
            scope="development",
            runtime_abi=SPAN_RUNTIME_ABI,
            source_import_policy=SOURCE_IMPORT_VERSION,
            compatibility=dict(
                runtime_abi=SPAN_RUNTIME_ABI,
                quantization="fp32",
                execution_device="cpu",
                max_resident_bytes=MAX_RESIDENT_BYTES,
            ),
            output_mode="typed_source_field_review",
            field_type=field_type,
            basis=basis,
            selection_policy=POLICY,
            producer="model_span_with_host_type_and_context_checks",
            transport="private_anonymous_pipes",
            production_admitted=False,
            trained_specialist_adapter=False,
            full_evidence_review_accepted=False,
            review_required=True,
            full_context_required_for_review=True,
            model_sha256=next(r.sha256 for r in worker.files if r.path.name == "model.safetensors"),
            inventory_sha256=digest(
                [dict(name=r.path.name, sha256=r.sha256, bytes=r.bytes) for r in worker.files]
            ),
        )
        self._binding = digest(self.model_binding)

    def generate_response(self, prompt):
        fail("compact_approved_source_objects_required")

    def generate_bound_response(self, prompt, *, question, sources, matter_id):
        if not isinstance(sources, tuple) or any(
            not isinstance(s, ContextSource)
            or not isinstance(s.metadata, dict)
            or s.metadata.get("matter_id", matter_id) != matter_id
            for s in sources
        ):
            fail("compact_extract_scope_invalid")
        if digest(self.model_binding) != self._binding or (self.field_type, self.basis) != (
            self.model_binding["field_type"],
            self.model_binding["basis"],
        ):
            fail("typed_field_contract_changed")
        bound = tuple(replace(s, metadata={**s.metadata, "matter_id": matter_id}) for s in sources)
        passages = field_passages(bound, matter_id)
        rank_input(question, passages, matter_id)  # Screen every source before any dispatch.
        state = digest(source_state(bound, matter_id))
        if not self._operation.acquire(blocking=False):
            fail("worker_busy")
        self._cancel.clear()
        try:
            rows = []
            for passage in passages:
                if self._cancel.is_set():
                    fail("generation_canceled")
                rows.extend(
                    self.worker.extract(
                        query=question,
                        passages=[passage],
                        matter_id=matter_id,
                        cancellation=self._cancel,
                    )
                )
            if self._cancel.is_set():
                fail("generation_canceled")
            if state != digest(source_state(bound, matter_id)):
                fail("compact_extract_source_changed")
            verify_field_output(
                tuple(rows),
                bound,
                question=question,
                matter_id=matter_id,
                field_type=self.field_type,
                basis=self.basis,
            )
            return SourceFieldResponse(
                text="Research source-field candidates: "
                + ", ".join(f"[{i}]" for i in range(1, len(bound) + 1))
                + ". Review required.",
                provider_id=self.provider_id,
                model_id=self.model_name,
                endpoint_class=self.endpoint.endpoint_class,
                finish_reason="stop",
                field_type=self.field_type,
                basis=self.basis,
                field_rows=tuple(rows),
            )
        finally:
            self._operation.release()

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
        self._cancel.set()
        self.worker.cancel()

    def release(self):
        self.worker.close()
