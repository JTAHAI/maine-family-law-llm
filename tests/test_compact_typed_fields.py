from hashlib import sha256

import pytest

from legal.fast_interchange.compact_cpu import LocalModelError
from legal.fast_interchange.compact_field_review import field_matches, review_field
from scripts.compact_typed_field_challenge import CASES
from scripts.verify_compact_typed_fields import validate_cases


@pytest.mark.parametrize(
    "kind,text",
    [
        ("clock_time", "08:35"),
        ("clock_time", "11:45 pm"),
        ("clock_time", "6 p.m."),
        ("calendar_date", "2024-02-29"),
        ("calendar_date", "April 14"),
        ("money", "85 dollars"),
        ("money", "$1,234.56"),
    ],
)
def test_explicit_narrow_field_forms(kind, text):
    assert field_matches(kind, text)


@pytest.mark.parametrize(
    "kind,text",
    [
        ("clock_time", "April 14"),
        ("clock_time", "25:00"),
        ("clock_time", "6:99"),
        ("clock_time", "17:00 pm"),
        ("clock_time", "6"),
        ("clock_time", "08:35 or 09:10"),
        ("calendar_date", "08:35"),
        ("calendar_date", "2023-02-29"),
        ("calendar_date", "April 31"),
        ("calendar_date", "4/5"),
        ("money", "85"),
        ("money", "$12,34"),
        ("money", "$1234,567"),
        ("money", "85 euros"),
        ("unknown", "08:35"),
    ],
)
def test_ambiguous_invalid_and_wrong_field_types_are_not_accepted(kind, text):
    assert not field_matches(kind, text)


def request(text="The fictional bus arrived at 08:35."):
    start = text.index("08:35")
    return dict(
        field_type="clock_time",
        basis="reported_event",
        query="When did the bus arrive?",
        matter_id="fictional-field",
        passage=dict(
            source_id="field", matter_id="fictional-field", lane="private_record", text=text
        ),
        span=dict(
            source_id="field",
            source_index=0,
            source_sha256=sha256(text.encode()).hexdigest(),
            status="candidate_span",
            text="08:35",
            start=start,
            end=start + 5,
            span_minus_null_score=2.0,
            review_required=True,
            truth_verified=False,
            absence_verified=False,
        ),
    )


def test_candidate_is_not_truth_or_source_assertion_verification():
    result = review_field(**request())
    assert result["status"] == "candidate_for_review"
    for key in (
        "truth_verified",
        "absence_verified",
        "legal_claims_verified",
        "source_assertion_verified",
        "production_admitted",
    ):
        assert result[key] is False
    assert result["review_required"] is True


@pytest.mark.parametrize(
    "text",
    [
        "The fictional bus was scheduled to arrive at 08:35.",
        "The fictional witness claimed the bus arrived at 08:35.",
        "If the fictional bus arrived at 08:35, the meeting would occur later.",
        "The fictional bus arrived at 08:35 according to an unverified note.",
        "The fictional bus did not arrive at 08:35.",
    ],
)
def test_qualified_excerpt_fails_closed(text):
    result = review_field(**request(text))
    assert result["status"] == "withheld" and result["candidate"] is None


def test_conservative_loss_of_useful_context_is_visible_not_claimed_solved():
    result = review_field(**request("The bus was scheduled for 08:00 but arrived at 08:35."))
    assert result["status"] == "withheld"
    assert result["blockers"] == ["excerpt_has_plan_conditional_or_attribution_language"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("basis", "established_fact"),
        ("basis", True),
        ("field_type", "legal_finding"),
        ("field_type", []),
    ],
)
def test_unsupported_or_factual_request_contract_is_rejected(key, value):
    data = request()
    data[key] = value
    with pytest.raises(LocalModelError):
        review_field(**data)


def test_source_tampering_and_wrong_matter_fail_before_review():
    data = request()
    data["span"]["text"] = "09:40"
    with pytest.raises(LocalModelError):
        review_field(**data)
    data = request()
    data["passage"]["matter_id"] = "another-matter"
    with pytest.raises(LocalModelError):
        review_field(**data)


def test_request_hash_binds_explicit_type_and_basis():
    data = request()
    original = review_field(**data)
    data["basis"] = "source_field"
    assert review_field(**data)["request_sha256"] != original["request_sha256"]
    data["field_type"] = "calendar_date"
    result = review_field(**data)
    assert result["status"] == "withheld"
    assert result["request_sha256"] != original["request_sha256"]


def test_fresh_challenge_has_no_duplicate_ids_and_balanced_targets():
    validate_cases(CASES)
    assert len(CASES) == len({r[0] for r in CASES}) == 24
    assert sum(r[-1] is None for r in CASES) == 12
    assert all(expected is None or expected in text for _, _, _, _, text, expected in CASES)


@pytest.mark.parametrize("change", ["missing", "duplicate", "answer", "basis", "balance"])
def test_challenge_mutation_is_not_silently_evaluated(change):
    rows = list(CASES)
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[-1] = rows[-2]
    else:
        row = list(rows[0])
        if change == "answer":
            row[-1] = "not in supplied source"
        elif change == "basis":
            row[2] = "established_fact"
        else:
            row[-1] = None
        rows[0] = tuple(row)
    with pytest.raises(ValueError):
        validate_cases(rows)


@pytest.mark.parametrize("row", [None, [], {}, "short"])
def test_malformed_fixture_rows_fail_with_safe_validation(row):
    rows = list(CASES)
    rows[0] = row
    with pytest.raises(ValueError, match="typed_fixture"):
        validate_cases(rows)
