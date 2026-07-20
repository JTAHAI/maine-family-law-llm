from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api
from maine_family_law_llm.intake_understanding import MAX_INTAKE_CHARS, parse_intake


def _citation(source_id: str, title: str, lane: str = "legal_authority") -> dict[str, object]:
    return {
        "source_id": source_id,
        "title": title,
        "snippet": f"Verified excerpt for {title}.",
        "metadata": {
            "source_lane": lane,
            "official": lane == "legal_authority",
            "jurisdiction": "Maine" if lane == "legal_authority" else "",
        },
    }


def _seed_answer(session_id: str) -> dict[str, object]:
    request = api.AskRequest(
        question="What Maine sources apply?",
        search_mode="maine_law",
        session_id=session_id,
    )
    return api._finalize_family_response(
        {
            "question": request.question,
            "answer_style": request.answer_style,
            "search_mode": "maine_law",
            "response_kind": "family_answer",
            "answer": "The answer must be reviewed against the source cards.",
            "grounded": True,
            "failure_class": "none",
            "citations": [
                _citation("ME-1", "First source"),
                _citation("ME-2", "Second source"),
            ],
            "review_required": True,
            "metadata": {},
        },
        request,
    )


def test_safety_language_outranks_served_paper_routing() -> None:
    summary = parse_intake(
        "I was served today, but I am not safe and there is a weapon in the house.",
        reference_date=date(2026, 7, 19),
    )
    assert summary.task == "immediate_safety"
    assert summary.attention_level == "emergency_or_urgent_safety"
    assert "immediate_safety" in summary.urgency_flags
    assert "served_papers" in summary.urgency_flags
    assert summary.routing_reasons[0] == "explicit immediate-safety language"


def test_negation_does_not_create_service_or_hearing_urgency() -> None:
    summary = parse_intake("I was not served and there is no hearing scheduled.")
    assert summary.task == "describe_situation"
    assert "served_papers" not in summary.urgency_flags
    assert "possible_deadline" not in summary.urgency_flags
    assert summary.procedural_posture == "unknown"

    safety = parse_intake("There is no immediate danger and no weapon is present.")
    assert safety.task != "immediate_safety"
    assert "immediate_safety" not in safety.urgency_flags


def test_event_dates_are_classified_by_nearest_phrase() -> None:
    summary = parse_intake(
        "I received court papers on July 18, 2026. My response is due July 27, 2026 "
        "and the hearing is August 3, 2026.",
        reference_date=date(2026, 7, 19),
    )
    assert [(row["kind"], row["normalized_date"]) for row in summary.critical_dates] == [
        ("service_date", "2026-07-18"),
        ("response_or_filing_deadline", "2026-07-27"),
        ("hearing_date", "2026-08-03"),
    ]
    assert summary.attention_level == "prompt_deadline_review"
    assert summary.procedural_posture == "initial_complaint"


def test_source_card_followup_reuses_legal_answer_and_selects_one_card() -> None:
    first = _seed_answer("v330-legal-source-session")
    followup = api.ask(
        api.AskRequest(
            question="Open the second one",
            search_mode="maine_law",
            session_id="v330-legal-source-session",
            last_search_id=str(first["search_id"]),
        )
    )
    assert followup["response_kind"] == "source_card_followup"
    assert followup["failure_class"] == "none"
    assert followup["source_card_count"] == 1
    assert followup["citations"][0]["source_id"] == "ME-2"
    assert followup["metadata"]["selected_source_card"] == 2
    assert "No new search was run" in followup["answer"]


def test_source_card_memory_is_session_scoped_and_requires_explicit_session() -> None:
    _seed_answer("v330-session-a")
    other = api.ask(
        api.AskRequest(
            question="show sources",
            search_mode="maine_law",
            session_id="v330-session-b",
        )
    )
    assert other["failure_class"] == "no_recent_search_result"

    no_session = api.ask(api.AskRequest(question="show sources", search_mode="maine_law"))
    assert no_session["failure_class"] == "conversation_session_required"


def test_new_chat_clear_endpoint_removes_in_memory_source_state() -> None:
    first = _seed_answer("v330-clear-session")
    assert first["source_card_count"] == 2
    cleared = api.clear_chat_session(api.ClearSessionRequest(session_id="v330-clear-session"))
    assert cleared["status"] == "cleared"
    assert cleared["session_state_removed"] is True
    assert cleared["persisted_to_disk"] is False

    followup = api.ask(
        api.AskRequest(
            question="show sources",
            search_mode="maine_law",
            session_id="v330-clear-session",
        )
    )
    assert followup["failure_class"] == "no_recent_search_result"


def test_stale_or_out_of_range_source_reference_fails_closed() -> None:
    first = _seed_answer("v330-stale-source-session")
    stale = api.ask(
        api.AskRequest(
            question="show sources",
            search_mode="maine_law",
            session_id="v330-stale-source-session",
            last_search_id="different-search-id",
        )
    )
    assert stale["failure_class"] == "stale_source_card_reference"
    assert stale["source_card_count"] == 0

    out_of_range = api.ask(
        api.AskRequest(
            question="Open the third one",
            search_mode="maine_law",
            session_id="v330-stale-source-session",
            last_search_id=str(first["search_id"]),
        )
    )
    assert out_of_range["failure_class"] == "source_card_selection_out_of_range"
    assert out_of_range["metadata"]["available_source_cards"] == 2


def test_long_intake_is_bounded_and_disclosed() -> None:
    summary = parse_intake("x" * (MAX_INTAKE_CHARS + 500))
    assert len(summary.normalized_text) == MAX_INTAKE_CHARS
    assert summary.input_truncated is True
    assert summary.original_length == MAX_INTAKE_CHARS + 500
    assert any("limited" in reason for reason in summary.routing_reasons)


def test_api_security_headers_and_error_payload_do_not_leak_exception_text(monkeypatch) -> None:
    client = TestClient(api.app, raise_server_exceptions=False)
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store, max-age=0"
    assert health.headers["cross-origin-opener-policy"] == "same-origin"
    assert health.headers["x-request-id"]

    def explode(_payload):
        raise RuntimeError("SECRET-CLIENT-PATH-C:/private/matter.pdf")

    monkeypatch.setattr(api, "ask", explode)
    failed = client.post("/api/chat", json={"question": "test"})
    assert failed.status_code == 500
    payload = failed.json()
    assert payload["detail"] == "internal_server_error"
    assert "error_class" not in payload
    assert payload["request_id"]
    assert "SECRET-CLIENT-PATH" not in failed.text


def test_ui_renders_date_extraction_with_verification_warning() -> None:
    js = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "maine_family_law_llm"
        / "ui"
        / "workbench.js"
    ).read_text(encoding="utf-8")
    assert "Dates and deadlines I heard" in js
    assert "This extraction is not a deadline calculation" in js
    assert "requested_actions" in js
    assert "/api/session/clear" in js
    assert "localSessionId = createLocalSessionId()" in js
