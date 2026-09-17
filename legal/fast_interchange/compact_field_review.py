"""Research-only typed-field hypothesis; not a fact or legal verifier.

The caller must explicitly choose field and source-report basis. No automatic
intent detection or public API/factory registration. Whole-excerpt uncertainty
screening intentionally may withhold valid fields; evaluate that lost coverage.
"""

import re
from datetime import date
from hashlib import sha256

from .admission import canonical
from .compact_cpu import fail
from .compact_reranker import rank_input
from .compact_span_process import verify_spans

POLICY = "typed_source_field_research_v1"
FIELDS = frozenset({"clock_time", "calendar_date", "money"})
BASES = frozenset({"source_field", "reported_event"})
UNCERTAINTY = re.compile(r"\b(?:no|not|unknown|missing|blank|unresolved|discrepancy)\b", re.I)
NON_EVENT = re.compile(
    r"\b(?:scheduled?|plans?|planned|proposed|requested|asks?|claim|claimed|claims|unverified|alleged|"
    r"expected|would|could|if|should|might|supposed|intended|estimate|estimated)\b",
    re.I,
)
EVENT = re.compile(
    r"\b(?:arrived|received|paid|began|ended|occurred|delivered|entered|recorded|completed)\b", re.I
)
MONTHS = {
    name: i
    for i, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        1,
    )
}


def field_matches(kind, value):
    if not isinstance(value, str) or not value or len(value) > 160:
        return False
    if kind == "clock_time":
        match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?", value, re.I)
        if not match:
            return False
        hour, minute, meridiem = match.groups()
        return (
            (1 <= int(hour) <= 12 if meridiem else 0 <= int(hour) <= 23)
            and (minute is not None or meridiem is not None)
            and (minute is None or 0 <= int(minute) <= 59)
        )
    if kind == "calendar_date":
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                date.fromisoformat(value)
                return True
            match = re.fullmatch(r"([A-Za-z]+) (\d{1,2})(?:,? (\d{4}))?", value)
            if not match or match[1].casefold() not in MONTHS:
                return False
            # A missing year remains missing. 2000 only checks possible day/month;
            # no inferred year or normalized date is returned to the caller.
            date(int(match[3] or 2000), MONTHS[match[1].casefold()], int(match[2]))
            return True
        except ValueError:
            return False
    if kind == "money":
        return bool(
            re.fullmatch(
                r"(?:\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?(?: dollars)?|"
                r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})? dollars)",
                value,
                re.I,
            )
        )
    return False


def review_field(*, field_type, basis, query, passage, matter_id, span):
    if (
        type(field_type) is not str
        or field_type not in FIELDS
        or type(basis) is not str
        or basis not in BASES
    ):
        fail("typed_field_contract_invalid")
    packet = rank_input(query, [passage], matter_id)
    verify_spans([span], packet)
    context = packet["passages"][0]["text"]
    blockers = []
    if span["status"] != "candidate_span":
        blockers.append("model_did_not_identify_candidate")
    elif not field_matches(field_type, span["text"]):
        blockers.append("candidate_field_type_mismatch")
    if UNCERTAINTY.search(context):
        blockers.append("excerpt_has_uncertainty_or_absence_language")
    if basis == "reported_event":
        if NON_EVENT.search(context):
            blockers.append("excerpt_has_plan_conditional_or_attribution_language")
        if not EVENT.search(context):
            blockers.append("explicit_event_wording_not_identified")
    return dict(
        policy=POLICY,
        request_sha256=sha256(
            canonical(dict(policy=POLICY, packet=packet, field_type=field_type, basis=basis))
        ).hexdigest(),
        status="withheld" if blockers else "candidate_for_review",
        blockers=blockers,
        candidate=None if blockers else dict(span),
        source_id=passage["source_id"],
        source_sha256=span["source_sha256"],
        review_required=True,
        truth_verified=False,
        absence_verified=False,
        legal_claims_verified=False,
        source_assertion_verified=False,
        production_admitted=False,
    )
