from __future__ import annotations

from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.family_answer_contract import build_family_answer_contract


def test_workboard_keeps_prompt_context_and_source_lanes_separate() -> None:
    contract = build_family_answer_contract(
        question=(
            "I was served with fictional family papers. The notice says October 7, 2026. "
            "I have a signed order and a fictional email export. What should I organize?"
        ),
        legacy_answer="Review the complete papers and source cards.",
        citations=[
            {
                "source_id": "ME-FIXTURE-RULE-1",
                "title": "Fixture Maine rule",
                "snippet": "Synthetic official source text.",
                "metadata": {"source_lane": "legal_authority", "official": True},
            },
            {
                "source_id": "REC-FIXTURE-ORDER-1",
                "title": "Fictional signed order",
                "snippet": "Synthetic private-record text.",
                "metadata": {"source_lane": "private_record", "source_locator": "fixture-order.pdf#page=1"},
            },
        ],
        search_mode="both",
        child_impact_enabled=True,
    )

    workboard = contract["conversation_workboard"]
    assert workboard["schema_version"] == "conversation_workboard_v1"
    assert workboard["analysis_type"] == "deterministic_local_intake_analysis"
    assert workboard["review_required"] is True
    assert workboard["stage"]["value"] != "Not established from this conversation"
    assert any(item["label"] == "October 7, 2026" for item in workboard["date_candidates"])
    assert all(item["review_state"] == "confirm_against_original_or_docket" for item in workboard["date_candidates"])

    lanes = {item["lane"]: item for item in workboard["source_lanes"]}
    assert lanes["Maine law"]["source_ids"] == ["ME-FIXTURE-RULE-1"]
    assert lanes["Matter records"]["source_ids"] == ["REC-FIXTURE-ORDER-1"]
    assert "does not establish facts" in workboard["boundary"]
    assert "deadline" in workboard["boundary"]
    assert "safety, predictability, and routine" in workboard["child_impact_prompt"]


def test_workboard_is_rendered_in_both_production_ui_asset_roots() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        Path("maine_family_law_llm/ui/workbench.js"),
        Path("src/maine_family_law_llm/ui/workbench.js"),
        Path("maine_family_law_llm/ui/workbench.css"),
        Path("src/maine_family_law_llm/ui/workbench.css"),
    ):
        content = (root / relative).read_text(encoding="utf-8")
        assert "conversation_workboard_v1" in content or "chat-conversation-workboard" in content

    js = (root / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "renderConversationWorkboard(structured.conversation_workboard)" in js
    assert "bindConversationWorkboard(wrapper, payload?.structured_answer?.conversation_workboard)" in js
    assert "data-workboard-lane" in js
    assert "sourceIds.join(' ')" in js
    assert "sourceIdentity(item)" in js


def test_chat_api_returns_the_workboard_for_a_fictional_served_papers_journey() -> None:
    payload = api.ask(
        api.AskRequest(
            question=(
                "I was served with fictional family court papers and a hearing notice for "
                "October 7, 2026. What should I organize?"
            ),
            search_mode="maine_law",
            session_id="synthetic-workboard-api-proof",
        )
    )

    workboard = payload["structured_answer"]["conversation_workboard"]
    assert payload["response_kind"] == "family_answer"
    assert workboard["schema_version"] == "conversation_workboard_v1"
    assert workboard["review_required"] is True
    assert workboard["date_candidates"][0]["label"] == "October 7, 2026"
    assert all(lane["review_action"] for lane in workboard["source_lanes"])
