from __future__ import annotations

import json
import re
import time

import pytest


def _frames(body: str) -> list[tuple[str, dict[str, object]]]:
    parsed: list[tuple[str, dict[str, object]]] = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        event = "message"
        data = ""
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            if line.startswith("data:"):
                data += line.split(":", 1)[1].strip()
        if data:
            parsed.append((event, json.loads(data)))
    return parsed


def test_ask_stream_emits_safe_progress_then_the_canonical_result() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    response = client.post(
        "/ask/stream",
        json={
            "question": "What Maine sources should I check for child support?",
            "search_mode": "maine_law",
            "session_id": "streaming-test-session",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response.text)
    names = [name for name, _payload in frames]
    assert names[:2] == ["accepted", "retrieving"]
    assert names[-2:] == ["result", "complete"]

    accepted = frames[0][1]
    assert accepted["local_only"] is True
    assert accepted["review_required"] is True
    assert accepted["first_feedback_budget_ms"] == api.STREAM_FIRST_FEEDBACK_BUDGET_MS == 150
    assert accepted["server_elapsed_ms"] == 0
    assert "Question received locally" in str(accepted["message"])

    result = frames[-2][1]
    answer = result["payload"]
    assert isinstance(answer, dict)
    assert answer["grounded"] is True
    assert answer["citations"]
    assert answer.get("review_required", True) is True
    assert isinstance(result["duration_ms"], int)
    assert "C:\\\\" not in response.text


def test_stream_first_feedback_precedes_a_slow_canonical_answer() -> None:
    """The performance promise is testable without making the answer less safe."""
    from maine_family_law_llm import api

    ran_answer = False

    def slow_answer(_payload: object) -> dict[str, object]:
        nonlocal ran_answer
        ran_answer = True
        time.sleep(0.2)
        return {"answer": "Verified result", "review_required": True}

    events = iter(api.iter_stream_answer_events(api.AskRequest(question="Fictional question"), slow_answer))
    started_at = time.perf_counter()
    first_event = next(events)
    first_feedback_ms = (time.perf_counter() - started_at) * 1000

    assert first_feedback_ms < api.STREAM_FIRST_FEEDBACK_BUDGET_MS
    assert ran_answer is False
    assert _frames(first_event)[0][0] == "accepted"
    assert _frames(first_event)[0][1]["first_feedback_budget_ms"] == 150

    assert _frames(next(events))[0][0] == "retrieving"
    assert ran_answer is False
    assert _frames(next(events))[0][0] == "result"
    assert ran_answer is True


def test_ask_stream_retains_cross_origin_and_size_protection() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from legal.security.local_request_firewall import DEFAULT_MAX_BODY_BYTES
    from maine_family_law_llm import api

    client = TestClient(api.app)
    cross_origin = client.post(
        "/ask/stream",
        headers={"host": "testserver", "origin": "https://evil.example"},
        json={"question": "This request must not reach the streaming handler."},
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json()["detail"] == "cross_origin_blocked"

    oversized = client.post(
        "/ask/stream",
        headers={"host": "testserver", "content-type": "application/octet-stream"},
        content=b"x" * (DEFAULT_MAX_BODY_BYTES + 1),
    )
    assert oversized.status_code == 413
    assert oversized.json()["detail"] == "request_too_large"


def test_fast_product_help_is_explicit_and_never_substitutes_for_legal_research() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    help_response = client.post("/ask", json={"question": "How do I import my records?"})
    assert help_response.status_code == 200
    help_payload = help_response.json()
    assert help_payload["response_kind"] == "local_help_fast_path"
    assert help_payload["grounded"] is False
    assert help_payload["review_required"] is True
    assert help_payload["matter_context_used"] is False
    assert help_payload["source_card_count"] == 0
    assert help_payload["metadata"]["fast_path"]["route_id"] == "import_records"
    assert help_payload["metadata"]["fast_path"]["retrieval_skipped"] is True
    assert help_payload["metadata"]["fast_path"]["artifact_reference"] == "workbench_drawer:setup"
    assert help_payload["metadata"]["fast_path_actions"] == [{"panel": "setup", "label": "Open matter setup"}]

    legal_response = client.post("/ask", json={"question": "What are Maine's best-interest factors?"})
    assert legal_response.status_code == 200
    assert legal_response.json()["response_kind"] != "local_help_fast_path"


def test_progressive_response_keeps_one_finalized_citation_basis() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    response = TestClient(api.app).post(
        "/ask",
        json={"question": "What Maine sources should I check for child support?", "search_mode": "maine_law"},
    )
    assert response.status_code == 200
    payload = response.json()
    progressive = payload["metadata"]["progressive_response"]
    assert progressive["schema_version"] == "progressive_response_v1"
    assert progressive["compact_view"] == "what_this_means_and_exact_source_cards"
    assert progressive["same_cited_basis"] is True
    assert progressive["review_required"] is True
    assert progressive["source_card_count"] == payload["source_card_count"] == len(payload["citations"])
    assert re.fullmatch(r"[0-9a-f]{64}", progressive["source_basis_sha256"])
    assert "what_to_do_right_now" in progressive["expandable_sections"]


def test_safe_context_compaction_is_session_scoped_no_prose_and_inspectable() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    session_id = "context-compaction-test-session"
    question = "What Maine sources should I check for child support?"
    answer = client.post("/ask", json={"question": question, "session_id": session_id})
    assert answer.status_code == 200
    search_id = answer.json()["search_id"]

    compact = client.post(
        "/api/conversation/context/compact",
        json={"session_id": session_id, "expected_search_id": search_id},
    )
    assert compact.status_code == 200
    receipt = compact.json()
    assert receipt["schema_version"] == "safe_conversation_context_v1"
    assert receipt["raw_turn_text_stored"] is False
    assert receipt["fact_promotion"] == "prohibited"
    assert receipt["review_required"] is True
    assert receipt["matter_scope"] == api._conversation_matter_scope()
    assert question not in json.dumps(receipt)
    assert re.fullmatch(r"[0-9a-f]{32}", receipt["context_id"])
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["source_basis_sha256"])

    inspected = client.get(f"/api/conversation/context/{session_id}")
    assert inspected.status_code == 200
    assert inspected.json()["context_id"] == receipt["context_id"]

    missing = client.post("/api/conversation/context/compact", json={"session_id": "not-a-real-session"})
    assert missing.status_code == 404


def test_intent_receipt_is_visible_and_marks_mixed_requests_for_review() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    navigation = client.post("/ask", json={"question": "How do I import my records?"}).json()
    assert navigation["metadata"]["answer_intent"]["primary_intent"] == "navigate"
    assert navigation["metadata"]["answer_intent"]["routing_changed"] is False

    mixed = client.post("/ask", json={"question": "Compare these records and calculate the deadline."}).json()
    intent = mixed["metadata"]["answer_intent"]
    assert intent["primary_intent"] == "mixed"
    assert intent["ambiguity"] is True
    assert intent["clarification_required"] is True
    assert intent["review_required"] is True
    clarification = mixed["metadata"]["clarification_minimizer"]
    assert clarification["required"] is True
    assert len(clarification["questions"]) == 1
    assert clarification["questions"][0]["question"] == "Which one task should be handled first?"
    assert len(clarification["questions"][0]["options"]) == 2


def test_actionable_footer_opens_a_safe_local_review_workspace() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    response = client.post(
        "/ask",
        json={"question": "What Maine sources should I check for child support?", "search_mode": "maine_law"},
    )
    assert response.status_code == 200
    footer = response.json()["metadata"]["actionable_footer"]
    assert footer["schema_version"] == "actionable_footer_v1"
    assert footer["next_action"]["panel"] == "evidence"
    assert footer["next_action"]["action_id"] == "open_evidence"
    assert footer["review_required"] is True
    assert "does not file, send, decide, or certify" in footer["boundary"]


def test_answer_correction_is_immutable_scoped_and_reruns_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    # This fixture deliberately exercises the general local workspace. A real
    # active matter additionally requires the privacy-safe audit write and
    # fails closed if that audit is unavailable.
    monkeypatch.setattr(api, "active_case_root", lambda: None)
    client = TestClient(api.app)
    session_id = "fictional-correction-session"
    answer = client.post(
        "/ask",
        json={
            "question": "What Maine sources should I check for child support?",
            "search_mode": "maine_law",
            "session_id": session_id,
        },
    ).json()
    base = {
        "session_id": session_id,
        "expected_search_id": answer["search_id"],
        "original_sentence": "The forms page is the only required source.",
        "proposed_correction": "Review the current official forms page and other applicable official authority before relying on a form.",
    }
    created = client.post(
        "/api/conversation/corrections",
        json={**base, "reason_code": "missing_context", "reason_note": "Fictional review note."},
    )
    assert created.status_code == 200
    receipt = created.json()
    assert receipt["schema_version"] == "conversation_answer_correction_v1"
    assert receipt["raw_correction_text_stored"] is False
    assert receipt["immutable"] is True
    assert receipt["review_required"] is True
    assert receipt["filing_ready"] is False
    assert re.fullmatch(r"[0-9a-f]{32}", receipt["correction_id"])
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["original_sentence_sha256"])
    assert receipt["original_verification"]["review_required"] is True
    assert receipt["citations"]

    rerun = client.post(f"/api/conversation/corrections/{receipt['correction_id']}/rerun", json=base)
    assert rerun.status_code == 200
    assert rerun.json()["review_required"] is True
    assert rerun.json()["proposed_verification"]["filing_ready"] is False

    mismatch = client.post(
        f"/api/conversation/corrections/{receipt['correction_id']}/rerun",
        json={**base, "proposed_correction": "Different fictional wording."},
    )
    assert mismatch.status_code == 409


def test_latency_observatory_keeps_prompt_and_matter_text_out_of_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    client = TestClient(api.app)
    session_id = "fictional-latency-session"
    answer = client.post("/ask", json={"question": "What Maine sources should I check?", "session_id": session_id}).json()
    response = client.post("/api/conversation/latency", json={
        "session_id": session_id, "expected_search_id": answer["search_id"],
        "first_feedback_ms": 22, "total_duration_ms": 148, "server_duration_ms": 121,
        "queue_delay_ms": 0, "cache_state": "miss", "model_output_tokens": 0,
        "hardware_concurrency": 8, "device_memory_gib": 16,
    })
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["prompt_text_stored"] is False
    assert receipt["matter_text_stored"] is False
    assert receipt["total_duration_ms"] == 148
    summary = client.get(f"/api/conversation/latency/{session_id}", params={"expected_search_id": answer["search_id"]})
    assert summary.status_code == 200
    assert summary.json()["observation_count"] == 1
    assert summary.json()["average_total_duration_ms"] == 148


def test_response_depth_preserves_source_basis_and_review_requirements() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    concise = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "response_depth": "concise"}).json()
    thorough = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "response_depth": "thorough"}).json()
    assert concise["metadata"]["response_depth"] == "concise"
    assert thorough["metadata"]["response_depth"] == "thorough"
    assert concise["metadata"]["progressive_response"]["source_basis_sha256"] == thorough["metadata"]["progressive_response"]["source_basis_sha256"]
    assert concise["review_required"] is True
    assert thorough["review_required"] is True


def test_audience_presentation_does_not_change_legal_truth_or_source_basis() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    client = TestClient(api.app)
    self_represented = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "audience": "self_represented"}).json()
    attorney = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "audience": "attorney_review"}).json()
    assert self_represented["metadata"]["audience_presentation"]["audience"] == "self_represented"
    assert attorney["metadata"]["audience_presentation"]["audience"] == "attorney_review"
    assert self_represented["metadata"]["audience_presentation"]["legal_truth_changed"] is False
    assert attorney["metadata"]["audience_presentation"]["legal_truth_changed"] is False
    assert self_represented["metadata"]["progressive_response"]["source_basis_sha256"] == attorney["metadata"]["progressive_response"]["source_basis_sha256"]
    assert self_represented["review_required"] is True
    assert attorney["review_required"] is True


def test_assumption_ledger_marks_unknowns_without_promoting_matter_facts() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    payload = TestClient(api.app).post("/ask", json={"question": "What Maine sources should I check for child support?"}).json()
    ledger = payload["metadata"]["assumption_ledger"]
    states = {item["entry_id"]: item["state"] for item in ledger["entries"]}
    assert ledger["review_required"] is True
    assert states["source_basis"] == "source_bound"
    assert states["matter_facts"] == "unknown"
    assert "does not alter records, facts, orders" in ledger["boundary"]


def test_answer_comparison_reuses_one_source_basis_without_storing_candidate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    client = TestClient(api.app)
    session_id = "fictional-comparison-session"
    answer = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "session_id": session_id}).json()
    comparison = client.post("/api/conversation/compare", json={
        "session_id": session_id, "expected_search_id": answer["search_id"],
        "approach_a": "Review the current official forms page.",
        "approach_b": "Review the current official forms page and verify applicable Maine authority.",
    })
    assert comparison.status_code == 200
    result = comparison.json()
    assert result["candidate_text_stored"] is False
    assert result["review_required"] is True
    assert result["filing_ready"] is False
    assert result["citations"]
    assert result["approach_a"]["verification"]["review_required"] is True


def test_conversation_branch_copies_only_source_lineage(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    client = TestClient(api.app)
    session_id = "fictional-branch-session"
    answer = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "session_id": session_id}).json()
    branch = client.post("/api/conversation/branch", json={"session_id": session_id, "expected_search_id": answer["search_id"]})
    assert branch.status_code == 200
    receipt = branch.json()
    assert receipt["raw_conversation_text_copied"] is False
    assert receipt["raw_matter_text_copied"] is False
    assert receipt["source_card_count"] == len(answer["citations"])
    assert receipt["branch_session_id"] != session_id
    inherited = client.post("/ask", json={"question": "Show my previous sources.", "session_id": receipt["branch_session_id"], "last_search_id": answer["search_id"]})
    assert inherited.status_code == 200


def test_source_bound_fact_pin_is_encrypted_matter_scoped_and_review_required(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(api.app)
    response = client.post("/api/fact-pins", json={
        "pin_id": "pin-fact-one", "label": "Fictional order date needs review", "effective_date": "2026-01-15",
        "dispute_status": "disputed", "actor_role": "self_represented",
        "source_ref": {"source_id": "fictional-order-001", "source_lane": "private_record", "locator": "page 2, paragraph 4", "source_hash": "a" * 64},
    })
    assert response.status_code == 200
    result = response.json()
    assert result["review_required"] is True
    assert result["fact_findings"] == "not_determined"
    assert result["source_drill_down"]["locator"] == "page 2, paragraph 4"
    encrypted = matter / "31_FACT_PINS" / "fact_pins.json.enc"
    assert encrypted.exists()
    assert "Fictional order date" not in encrypted.read_text(encoding="utf-8")
    assert client.get("/api/fact-pins/pin-fact-one").status_code == 200
    wrong_role = client.post("/api/fact-pins", json={
        "pin_id": "pin-fact-two", "label": "No role", "actor_role": "unknown",
        "source_ref": {"source_id": "fictional-order-002", "source_lane": "private_record", "locator": "page 3", "source_hash": "b" * 64},
    })
    assert wrong_role.status_code == 403


def test_compound_question_is_explicitly_decomposed_without_claiming_independent_research() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    response = TestClient(api.app).post("/ask", json={"question": "What Maine sources should I check for child support and how should I prepare for a hearing?"})
    assert response.status_code == 200
    receipt = response.json()["metadata"]["question_decomposition"]
    assert receipt["is_compound"] is True
    assert len(receipt["components"]) == 2
    assert all(part["independent_resolution"] == "not_yet_verified" for part in receipt["components"])
    assert receipt["private_question_persisted"] is False
    assert receipt["review_required"] is True


def test_conflicting_pinned_date_creates_a_review_prompt_without_deciding_truth(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(api.app)
    created = client.post("/api/fact-pins", json={
        "pin_id": "pin-order-date", "label": "Fictional order date", "effective_date": "2026-01-15",
        "dispute_status": "disputed", "actor_role": "self_represented",
        "source_ref": {"source_id": "fictional-order-001", "source_lane": "private_record", "locator": "page 2", "source_hash": "c" * 64},
    })
    assert created.status_code == 200
    answer = client.post("/ask", json={"question": "The fictional order date is 2026-02-01; what should I review?"})
    assert answer.status_code == 200
    receipt = answer.json()["metadata"]["contradiction_followup"]
    assert receipt["candidate_count"] == 1
    candidate = receipt["candidates"][0]
    assert candidate["pinned_date"] == "2026-01-15"
    assert candidate["new_date_candidates"] == ["2026-02-01"]
    assert candidate["source_ref"]["locator"] == "page 2"
    assert candidate["review_required"] is True
    assert "does not decide" in receipt["boundary"]


def test_usefulness_receipt_is_structural_and_not_human_review(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm import api

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    client = TestClient(api.app)
    session_id = "fictional-usefulness-session"
    answer = client.post("/ask", json={"question": "What Maine sources should I check for child support?", "session_id": session_id}).json()
    evaluation = client.post("/api/conversation/usefulness", json={"session_id": session_id, "expected_search_id": answer["search_id"]})
    assert evaluation.status_code == 200
    receipt = evaluation.json()
    assert receipt["answer_text_stored"] is False
    assert receipt["synthetic_or_human_review"] == "deterministic_structural_checks_only"
    assert receipt["review_required"] is True
    assert receipt["filing_ready"] is False
    assert "not attorney review" in receipt["boundary"]
    assert len(receipt["human_review_rubric"]) == 5


def test_retrieval_rank_receipt_preserves_real_component_contributions(monkeypatch: pytest.MonkeyPatch) -> None:
    from maine_family_law_llm import api

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    payload = api.AskRequest(question="What Maine authority applies?")
    result = api._finalize_family_response({
        "answer": "Review the source.", "citations": [{"source_id": "official-001", "title": "Fictional official authority", "score": 9.5, "metadata": {}, "method": "cached_lexical_authority_weighted", "rank": 1, "component_scores": {"cached_lexical": 9.2}, "explanation": "Lexical match with authority weighting."}],
    }, payload)
    source_meta = result["citations"][0]["metadata"]
    assert source_meta["retrieval_method"] == "cached_lexical_authority_weighted"
    assert source_meta["retrieval_component_scores"] == {"cached_lexical": 9.2}
    assert source_meta["negative_treatment_status"] == "negative_treatment_unknown"
    receipt = result["metadata"]["retrieval_rank_explainability"]
    assert receipt["contribution_detail_count"] == 1
    assert "do not prove" in receipt["boundary"]


def test_temporal_authority_review_blocks_undated_or_later_source_metadata() -> None:
    from maine_family_law_llm import api

    receipt = api._temporal_authority_receipt("What applied as of 2025-01-01?", [{"source_id": "fictional-rule", "metadata": {"source_lane": "legal_authority", "effective_date": "2026-01-01", "freshness_status": "fresh"}}])
    assert receipt["status"] == "blocked_needs_historical_source_review"
    assert receipt["historical_law_determined"] is False
    assert receipt["sources"][0]["status"] == "effective_after_requested_date"


def test_authority_conflict_receipt_only_flags_divergent_same_citation_metadata() -> None:
    from maine_family_law_llm import api

    receipt = api._authority_conflict_receipt([
        {"source_id": "one", "citation": "Fictional Rule 1", "metadata": {"source_lane": "legal_authority", "source_class": "court_rule", "effective_date": "2025-01-01", "freshness_status": "fresh"}},
        {"source_id": "two", "citation": "Fictional Rule 1", "metadata": {"source_lane": "legal_authority", "source_class": "court_rule", "effective_date": "2026-01-01", "freshness_status": "fresh"}},
    ])
    assert receipt["candidate_count"] == 1
    assert receipt["controlling_authority_determined"] is False


def test_stream_route_and_client_are_present_in_both_shipped_mirrors() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for relative in (
        "src/maine_family_law_llm/api.py",
        "maine_family_law_llm/api.py",
        "src/maine_family_law_llm/ui/workbench.js",
        "maine_family_law_llm/ui/workbench.js",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "/ask/stream" in text
    for relative in (
        "src/maine_family_law_llm/ui/workbench.js",
        "maine_family_law_llm/ui/workbench.js",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "fetchAnswerStream" in text
        assert "local_stream_incomplete" in text
        assert "CHAT_FIRST_FEEDBACK_BUDGET_MS = 150" in text
        assert "first_feedback_ms" in text
        assert "FAST_PATH_DRAWER_PANELS" in text
        assert "data-fast-path-panel" in text
        assert "renderProgressiveAnswerDetails" in text
        assert "same_cited_basis" in text
        assert "compactSafeConversationContext" in text
        assert "conversation_context_compaction" in text
        assert "answer_intent" in text
        assert "chat-intent-notice" in text
        assert "renderActionableFooter" in text
        assert "bindActionableFooter" in text
        assert "data-answer-footer-panel" in text
        assert "renderAnswerCorrectionControls" in text
        assert "bindAnswerCorrectionControls" in text
        assert "data-save-answer-correction" in text
        assert "recordChatLatency" in text
        assert "renderLatencyObservatory" in text
        assert "/api/conversation/latency" in text
        assert "responseDepth" in text
        assert "renderProgressiveAnswerDetails(payload, structured, {open" in text
        assert "renderAudiencePresentation" in text
        assert "audience: audience?.value" in text
        assert "renderClarificationMinimizer" in text
        assert "bindClarificationMinimizer" in text
        assert "data-clarification-prompt" in text
        assert "renderAssumptionLedger" in text
        assert "bindAssumptionLedger" in text
        assert "data-ledger-correct" in text
        assert "renderAnswerComparisonControls" in text
        assert "bindAnswerComparisonControls" in text
        assert "/api/conversation/compare" in text
        assert "renderConversationBranchControl" in text
        assert "bindConversationBranchControl" in text
        assert "/api/conversation/branch" in text
        assert "renderFactPinControl" in text
        assert "bindFactPinControl" in text
        assert "/api/fact-pins" in text
        assert "renderQuestionDecomposition" in text
        assert "bindQuestionDecomposition" in text
        assert "data-decomposed-question" in text
        assert "renderContradictionFollowup" in text
        assert "bindContradictionFollowup" in text
        assert "data-contradiction-followup" in text
        assert "renderUsefulnessControl" in text
        assert "bindUsefulnessControl" in text
        assert "/api/conversation/usefulness" in text
        assert "Why this source ranked here" in text
        assert "retrieval_component_scores" in text
        assert "renderQueryExpansionGuardrails" in text
        assert "Jurisdiction check:" in text
        assert "renderTemporalAuthorityReview" in text
        assert "historical source review" in text
        assert "negative_treatment_unknown" in text
        assert "renderAuthorityConflictReview" in text
