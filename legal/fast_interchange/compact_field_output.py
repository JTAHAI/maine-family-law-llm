"""Host-side typed field verification and honest, source-bound presentation."""

from hashlib import sha256

from .compact_clause_review import POLICY, review_clause
from .compact_cpu import fail
from .compact_extracts import digest, source_state
from .compact_field_review import BASES, FIELDS
from .compact_reranker import rank_input


def validate_contract(field_type, basis):
    if (
        type(field_type) is not str
        or field_type not in FIELDS
        or type(basis) is not str
        or basis not in BASES
    ):
        fail("typed_field_contract_invalid")


def field_passages(sources, matter_id):
    state = source_state(sources, matter_id)
    if any(row["instruction_like_text_detected"] for row in state):
        fail("compact_extract_instruction_blocked")
    return [
        dict(
            source_id=row["source_id"],
            matter_id=matter_id,
            lane=row["lane"],
            text=row["text"],
            metadata=row["metadata"],
        )
        for row in state
    ]


def verify_field_output(rows, sources, *, question, matter_id, field_type, basis):
    validate_contract(field_type, basis)
    passages = field_passages(sources, matter_id)
    rank_input(question, passages, matter_id)
    if not isinstance(rows, tuple) or len(rows) != len(passages):
        fail("typed_field_response_invalid")
    reviewed, spans = [], []
    for reference, (raw, passage) in enumerate(zip(rows, passages, strict=True), 1):
        # One source per model call gives index zero. No reindexing of untrusted
        # responses; the original id/hash and every other protocol field verify.
        result = review_clause(
            field_type=field_type,
            basis=basis,
            query=question,
            passage=passage,
            matter_id=matter_id,
            span=raw,
        )
        reviewed.append(dict(reference=reference, **result))
        if result["candidate"] is not None:
            candidate = result["candidate"]
            spans.append(
                dict(
                    source_id=passage["source_id"],
                    reference=reference,
                    start_offset=candidate["start"],
                    end_offset=candidate["end"],
                    source_text_sha256=candidate["source_sha256"],
                    quote_sha256=sha256(candidate["text"].encode()).hexdigest(),
                    status="exact",
                )
            )
    report = dict(
        schema_version="evidence_typed_fields_boundary_v1",
        status="source_fields_review_required",
        policy=POLICY,
        producer="model_span_with_host_type_and_context_checks",
        model_inference=True,
        deterministic_fallback_used=False,
        field_type=field_type,
        basis=basis,
        fields=reviewed,
        source_spans=spans,
        blockers=[],
        review_required=True,
        factual_claims_verified=False,
        legal_claims_verified=False,
        relevance_verified=False,
        absence_verified=False,
        source_assertion_verified=False,
        production_admitted=False,
        full_context_required_for_review=True,
        partial_extracts_available=False,
    )
    report["report_sha256"] = digest(report)
    return report


def withheld_reason(blockers):
    """Fixed recovery wording, never raw exceptions or a factual absence claim."""
    codes = set(blockers)
    if "model_did_not_identify_candidate" in codes:
        return "The model did not identify a source-text candidate."
    if "whole_excerpt_dispute_attribution_or_condition" in codes:
        return "The source contains dispute, attribution or conditional wording that needs review."
    if "excerpt_has_uncertainty_or_absence_language" in codes:
        return "The source contains uncertainty or missing-information wording."
    if "excerpt_has_plan_conditional_or_attribution_language" in codes:
        return "Planned, conditional or attributed wording cannot establish the requested event."
    if "explicit_event_wording_not_identified" in codes:
        return "The requested reported-event wording was not identified."
    if "candidate_field_type_mismatch" in codes:
        return "The selected text does not match the requested date, time or amount format."
    return "The candidate did not meet this limited source-field contract."


def render_field_output(report):
    field = {"clock_time": "time", "calendar_date": "date", "money": "amount"}[report["field_type"]]
    basis = {
        "source_field": "literal source field (not proof an event happened)",
        "reported_event": "reported-event wording (not an established finding)",
    }[report["basis"]]
    lines = [
        f"Research source-{field} review — {basis}.",
        "Producer: local QA model with host type/context checks; no deterministic fallback.",
        "Inspect the full original source, including qualifications. "
        "Facts, legal meaning and relevance are unverified.",
    ]
    for row in report["fields"]:
        if row["candidate"] is None:
            lines.append(
                f"[{row['reference']}] No supported {field} candidate was retained. "
                "This does not establish absence; inspect the source directly. "
                + withheld_reason(row["blockers"])
            )
        else:
            lines.append(
                f"[{row['reference']}] Source-text candidate: “{row['candidate']['text']}”. "
                "Not a verified fact."
            )
    return "\n\n".join([*lines, "Research only. Review required."])
