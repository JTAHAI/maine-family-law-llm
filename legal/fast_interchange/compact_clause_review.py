"""Research clause-context hypothesis; all original context remains bound.

This is not a sentence parser, assertion verifier or automatic public policy.
Global disputes/conditions cannot be dropped by selecting a narrower clause.
"""

import re
from hashlib import sha256

from .admission import canonical
from .compact_field_review import review_field
from .compact_reranker import rank_input
from .compact_span_process import verify_spans

POLICY = "typed_source_clause_research_v1"
# Keep disputes and attribution global, even if they follow the selected sentence.
GLOBAL_BLOCK = re.compile(
    r"\b(?:unverified|allegation|alleged|claims?|claimed|disputed|discrepancy|conflicting|"
    r"unresolved|incorrect|false|conditional|hypothetical|if|would|could|might|never|neither)\b"
    r"|\bnot\s+(?:correct|true|accurate|confirmed|verified)\b"
    r"|\bdid\s+not\s+(?:happen|occur|arrive|receive|pay|begin|end)\b",
    re.I,
)
BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|;\s*|\n+|\s+but\s+", re.I)


def containing_clause(text, start, end):
    left = 0
    for match in BOUNDARY.finditer(text):
        if left <= start < end <= match.start():
            return left, match.start()
        if start < match.end() and end > match.start():
            return None
        left = match.end()
    return (left, len(text)) if left <= start < end <= len(text) else None


def review_clause(*, field_type, basis, query, passage, matter_id, span):
    packet = rank_input(query, [passage], matter_id)
    verify_spans([span], packet)
    original = review_field(
        field_type=field_type,
        basis=basis,
        query=query,
        passage=passage,
        matter_id=matter_id,
        span=span,
    )
    context = passage["text"]
    scope = (
        containing_clause(context, span["start"], span["end"])
        if span["status"] == "candidate_span"
        else None
    )
    if scope is not None:
        left, right = scope
        sliced = dict(
            source_id=passage["source_id"],
            matter_id=matter_id,
            lane="private_record",
            text=context[left:right],
        )
        local_span = dict(
            span,
            start=span["start"] - left,
            end=span["end"] - left,
            source_sha256=sha256(sliced["text"].encode()).hexdigest(),
        )
        # Full original privacy and instruction screening already succeeded.
        # Do not apply full-record protected offsets to a newly sliced string.
        result = review_field(
            field_type=field_type,
            basis=basis,
            query=query,
            passage=sliced,
            matter_id=matter_id,
            span=local_span,
        )
    else:
        result = original
    if GLOBAL_BLOCK.search(context):
        result["blockers"].append("whole_excerpt_dispute_attribution_or_condition")
    if result["blockers"]:
        result.update(status="withheld", candidate=None)
    else:
        result["candidate"] = dict(span)
    result.update(
        policy=POLICY,
        source_sha256=span["source_sha256"],
        context_span=None if scope is None else dict(start=scope[0], end=scope[1]),
        full_context_sha256=sha256(context.encode()).hexdigest(),
        full_context_required_for_review=True,
        request_sha256=sha256(
            canonical(dict(policy=POLICY, packet=packet, field_type=field_type, basis=basis))
        ).hexdigest(),
    )
    return result
