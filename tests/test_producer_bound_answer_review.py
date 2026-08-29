"""Fictional source/API acceptance; not real legal-model evaluation."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_v560_authority_verification_workbench import _authority_root

from legal.answering.review_scope import AnswerAssertions, AnswerReviewScopes
from legal.verifiers.claim_support_verifier import _sentence_spans, extract_legal_claims

CLAIM = (
    "Parental rights and responsibilities are decided according to the best interest of the child."
)
SOURCE = "statute-19a-1653"


def test_quote_closer_and_metadata_are_separate_with_exact_offsets():
    text = f"“19-A M.R.S. § 1653. {CLAIM}” Freshness status: stale."
    spans = _sentence_spans(text)
    assert len(spans) == 3
    assert all(text[start:end] == body for start, end, body in spans)
    claims = extract_legal_claims(text)
    assert CLAIM in claims
    assert not any("Freshness" in claim for claim in claims)


@pytest.mark.parametrize("citation", ["M.R. Civ. P. 56", "M.R. App. P. 2", "M.R. Evid. 401"])
def test_legal_abbreviations_not_split(citation):
    text = f"The rule {citation} requires review. Another sentence."
    assert _sentence_spans(text)[0][2] == text.split(" Another")[0]


def test_workflow_heading_cannot_suppress_unknown_legal_claim():
    claim = "The court must always award a purple certificate."
    assert claim in extract_legal_claims("Workflow guidance:\n- " + claim)
    assert extract_legal_claims("Profile and supporter settings are displayed.") == []


def test_large_or_late_assertion_is_never_silently_omitted():
    claim = "The court must award " + "purple " * 1000 + "certificates."
    assert claim in extract_legal_claims(claim)
    late = "All filings are free."
    assert late in extract_legal_claims("An ordinary sentence. " * 1010 + late)


def test_partial_chat_support_is_a_blocker_not_just_a_warning():
    from maine_family_law_llm.answer_support_integrity import assess_answer_support_integrity

    report = assess_answer_support_integrity(
        "Rule 1 is titled Scope of Rules and governs purple certificates.",
        [
            {
                "source_id": SOURCE,
                "snippet": "Rule 1 is titled Scope of Rules.",
                "metadata": {"freshness_status": "fresh"},
            }
        ],
    )
    assert "candidate_legal_claims_only_partially_supported" in report["blockers"]
    assert report["filing_ready"] is False


def test_full_verification_required_when_compact_chat_budget_is_exhausted():
    from maine_family_law_llm.answer_support_integrity import assess_answer_support_integrity

    report = assess_answer_support_integrity(
        " ".join(f"Rule {n} requires review." for n in range(15)),
        [],
        max_claims=12,
    )
    assert report["candidate_legal_claim_total"] == 15
    assert "candidate_claim_review_incomplete_use_full_verification" in report["blockers"]


def test_scopes_are_context_bound_bounded_expiring_and_process_local():
    clock = [0.0]
    scopes = AnswerReviewScopes(ttl_seconds=10, max_entries=1, clock=lambda: clock[0])
    assertions = AnswerAssertions(CLAIM, "build-a", (SOURCE,))
    first = scopes.issue(answer=CLAIM, context="session-a", assertions=assertions)
    assert CLAIM not in first and "session" not in first
    assert scopes.resolve(first, answer=CLAIM, context="session-a").assertions == assertions
    for answer, context in [(CLAIM + " forged", "session-a"), (CLAIM, "session-b")]:
        with pytest.raises(ValueError, match="mismatch"):
            scopes.resolve(first, answer=answer, context=context)
    with pytest.raises(ValueError, match="unavailable"):
        AnswerReviewScopes().resolve(first, answer=CLAIM, context="session-a")
    second = scopes.issue(answer=CLAIM, context="session-a", assertions=assertions)
    with pytest.raises(ValueError, match="unavailable"):
        scopes.resolve(first, answer=CLAIM, context="session-a")
    clock[0] = 10
    with pytest.raises(ValueError, match="unavailable"):
        scopes.resolve(second, answer=CLAIM, context="session-a")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from maine_family_law_llm.api import app

    root = _authority_root(tmp_path)
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(root))
    monkeypatch.setenv("MFL_USE_ACTIVE_AUTHORITY_IN_SOURCE", "1")
    with TestClient(app) as session:
        yield session


def ask(client):
    result = client.post(
        "/ask",
        json={
            "question": "Explain 19-A M.R.S. § 1653",
            "search_mode": "maine_law",
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body.get("answer_review_scope"), body
    return body


def review_request(answer):
    return {
        "text": answer["answer"],
        "source_ids": [SOURCE],
        "answer_review_scope": answer["answer_review_scope"],
    }


def test_real_ask_to_canonical_review_excludes_producer_templates(client):
    answer = ask(client)
    result = client.post("/api/authority/verify-answer", json=review_request(answer))
    assert result.status_code == 200, result.text
    body = result.json()
    assert "verification_report" in body, body
    report = body["verification_report"]
    assert 1 <= len(report["claims"]) <= 2
    assert all(row["status"] == "supported" for row in report["claims"]), report
    assert all(
        "What to" not in row["claim"] and "Freshness" not in row["claim"]
        for row in report["claims"]
    )
    assert report["claim_extraction"]["producer_bound"] is True
    assert report["quotes"][0]["status"] == "exact_match"
    assert body["filing_gate"]["filing_ready"] is False
    assert body["review_required"] is True
    assert (
        body["verification_receipt"]["answer_sha256"] == report["claim_extraction"]["answer_sha256"]
    )
    assert client.get(f"/api/authority/sources/{SOURCE}").status_code == 200


@pytest.mark.parametrize("change", ["answer", "handle", "sources"])
def test_modified_answer_or_binding_cannot_reuse_scope(client, change):
    payload = review_request(ask(client))
    if change == "answer":
        payload["text"] += "\nWorkflow guidance: The court must award a purple certificate."
    elif change == "handle":
        payload["answer_review_scope"] = "invented-handle"
    else:
        payload["source_ids"] = ["different-source"]
    body = client.post("/api/authority/verify-answer", json=payload).json()
    assert body["status"] == "blocked", body
    assert body["review_required"] is True


def test_other_client_session_cannot_reuse_scope(client):
    payload = review_request(ask(client))
    body = client.post(
        "/api/authority/verify-answer", json=payload, headers={"X-MFLL-Client-Session": "b" * 64}
    ).json()
    assert body["status"] == "blocked", body


def test_oversized_legal_candidate_fails_closed(client):
    body = client.post(
        "/api/authority/verify-answer",
        json={
            "text": "The court must award " + "purple " * 4000 + "certificates.",
            "source_ids": [SOURCE],
            "claims": [CLAIM],
            "auto_extract_claims": False,
        },
    ).json()
    assert body["status"] == "blocked"
    assert "verification_claim_too_large" in body["blockers"]


def test_user_labels_and_explicit_claims_do_not_hide_added_assertion(client):
    unknown = "The court must award a purple certificate."
    text = CLAIM + "\nWorkflow guidance:\n- " + unknown
    body = client.post(
        "/api/authority/verify-answer",
        json={
            "text": text,
            "source_ids": [SOURCE],
            "claims": [CLAIM],
            "auto_extract_claims": False,
            "sections": [{"type": "guidance", "text": unknown}],
        },
    ).json()
    claims = body["verification_report"]["claims"]
    assert any(unknown in row["claim"] and row["supported"] is False for row in claims)
    assert body["filing_gate"]["filing_ready"] is False
    assert body["verification_report"]["claim_extraction"]["caller_labels_trusted"] is False


def test_scope_cannot_hide_a_changed_or_stale_authority_generation(tmp_path, monkeypatch):
    from app.services.authority_product_service import AuthorityProductService
    from legal.answering.review_scope import BoundAnswerReview, text_hash

    root = _authority_root(tmp_path)
    service = AuthorityProductService(data_root=root)
    active = service._active_product(verify_all=False)
    assertions = AnswerAssertions(CLAIM, active.build_id, (SOURCE,))
    bound = BoundAnswerReview(text_hash(CLAIM), "context", assertions, float("inf"))
    wrong = replace(bound, assertions=replace(assertions, authority_build_id="other-build"))
    result = service.verify_output(text=CLAIM, source_ids=[SOURCE], review_scope=wrong)
    assert result["status"] == "blocked"
    original = service._safe_source_card
    monkeypatch.setattr(
        service,
        "_safe_source_card",
        lambda row: {
            **original(row),
            "freshness_status": "stale",
            "authority_status": "stale",
        },
    )
    result = service.verify_output(text=CLAIM, source_ids=[SOURCE], review_scope=bound)
    assert any(row["status"] == "stale" for row in result["verification_report"]["claims"])
    assert result["filing_gate"]["filing_ready"] is False
