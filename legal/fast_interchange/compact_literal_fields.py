"""Explicit-label source lookup, not model inference or factual verification.

Only `Label: value` and `lists the Label as value` forms are recognized.
The operator supplies the exact label; no semantic label/intent guessing.
"""

import re
from hashlib import sha256

from .admission import canonical
from .compact_clause_review import GLOBAL_BLOCK
from .compact_cpu import fail
from .compact_field_review import FIELDS, UNCERTAINTY, field_matches
from .compact_reranker import rank_input

POLICY = "explicit_literal_field_lookup_research_v1"


def locate_literal_field(*, field_type, label, query, passage, matter_id):
    if (
        type(field_type) is not str
        or field_type not in FIELDS
        or type(label) is not str
        or re.fullmatch(r"[A-Za-z][A-Za-z -]{0,59}", label) is None
        or label != label.strip()
    ):
        fail("literal_field_contract_invalid")
    packet = rank_input(query, [passage], matter_id)
    text = packet["passages"][0]["text"]
    pattern = re.compile(
        rf"(?:^[ \t]*{re.escape(label)}[ \t]*:[ \t]*|\blists the {re.escape(label)} as )"
        r"(?P<value>[^\r\n;]+)",
        re.I | re.M,
    )
    matches = list(pattern.finditer(text))
    blockers, candidate = [], None
    if len(matches) != 1:
        blockers.append("literal_field_missing_or_ambiguous")
    elif GLOBAL_BLOCK.search(text) or UNCERTAINTY.search(text):
        blockers.append("whole_excerpt_uncertainty_dispute_attribution_or_condition")
    else:
        match = matches[0]
        raw = match["value"]
        value = raw.strip()
        start = match.start("value") + len(raw) - len(raw.lstrip())
        if not field_matches(field_type, value) and value.endswith("."):
            value = value[:-1]
        if not field_matches(field_type, value):
            blockers.append("literal_field_value_not_supported")
        else:
            candidate = dict(
                source_id=passage["source_id"],
                start=start,
                end=start + len(value),
                text=text[start : start + len(value)],
                source_sha256=sha256(text.encode()).hexdigest(),
                review_required=True,
                truth_verified=False,
            )
    return dict(
        policy=POLICY,
        producer="deterministic_literal_lookup",
        model_inference=False,
        status="withheld" if blockers else "candidate_for_review",
        candidate=candidate,
        blockers=blockers,
        review_required=True,
        truth_verified=False,
        source_assertion_verified=False,
        legal_claims_verified=False,
        absence_verified=False,
        production_admitted=False,
        source_id=passage["source_id"],
        full_context_required_for_review=True,
        full_context_sha256=sha256(text.encode()).hexdigest(),
        request_sha256=sha256(
            canonical(dict(policy=POLICY, packet=packet, field_type=field_type, label=label))
        ).hexdigest(),
    )
