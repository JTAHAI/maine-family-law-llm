from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_structured_answer_contract_keeps_law_and_private_records_separate() -> None:
    from maine_family_law_llm.family_answer_contract import (
        build_family_answer_contract,
        render_legacy_answer,
    )

    contract = build_family_answer_contract(
        question="I was served and need help with my child's school routine.",
        legacy_answer="A careful answer based on retrieved sources.",
        citations=[
            {"source_id": "law-1", "title": "Maine rule", "metadata": {"source_lane": "legal_authority", "official": True}},
            {"source_id": "record-1", "title": "Family email", "metadata": {"source_lane": "private_record"}},
        ],
        search_mode="both",
        safety={"requires_emergency_language": False},
        child_impact_enabled=True,
        lane_grounding={"legal_authority": True, "private_record": True},
    )

    assert contract["schema_version"] == "family_answer_v3"
    assert contract["lane_grounding"] == {"legal_authority": True, "private_record": True}
    assert contract["maine_law_sources"][0]["lane"] == "legal_authority"
    assert contract["private_record_sources"][0]["lane"] == "private_record"
    assert contract["safety_flags"]["served_papers"] is True
    assert contract["child_impact_lens"]
    rendered = render_legacy_answer(contract)
    assert "What this means" in rendered
    assert "Your next three steps" in rendered


def test_default_maine_law_response_is_not_routed_into_private_records() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(AskRequest(question="What are M.R. Civ. P.?"))
    assert payload["search_mode"] == "maine_law"
    assert payload["source_lanes"]["private_record"] is False
    assert all(item["metadata"]["source_lane"] == "legal_authority" for item in payload["citations"])
    assert "structured_answer" in payload


def test_combined_search_composes_raw_lanes_once(monkeypatch) -> None:
    from maine_family_law_llm import api

    def legal_lane(payload, *, finalize: bool = True):
        assert finalize is False
        return {
            "question": payload.question,
            "answer": "Maine-law source answer.",
            "grounded": True,
            "safety": {},
            "citations": [{"source_id": "law", "title": "Maine authority"}],
            "metadata": {},
        }

    def record_lane(payload, *, finalize: bool = True):
        assert finalize is False
        return {
            "answer": "Private-record answer.",
            "grounded": True,
            "citations": [{"source_id": "record", "title": "Case record"}],
            "active_case_root": "C:/case",
            "active_case_label": "Example matter",
        }

    monkeypatch.setattr(api, "_general_law_payload", legal_lane)
    monkeypatch.setattr(api, "_active_case_chat_payload", record_lane)

    result = api.ask(api.AskRequest(question="What happened?", search_mode="both"))

    assert result["answer"].count("What this means") == 1
    assert "Maine-law source answer." in result["answer"]
    assert "Private-record answer." in result["answer"]
    assert result["source_lanes"] == {"legal_authority": True, "private_record": True}


def test_v3_composer_and_drawer_requirements_are_present() -> None:
    html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    css = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.css").read_text(encoding="utf-8")

    assert 'data-search-mode="maine_law"' in html
    assert 'data-search-mode="my_records"' in html
    assert 'data-search-mode="both"' in html
    assert 'id="child-impact-lens"' in html
    assert 'id="stop-button"' in html
    assert 'id="clear-draft-button"' in html
    assert 'Clear visible conversation' in html
    assert "activeRequestController?.abort()" in js
    assert "Choose an active matter before searching private records." in js
    assert "data-open-evidence" in js
    assert ".search-mode-segmented" in css
    assert ".child-impact-answer" in css
    assert 'class="composer-controls"' in html
    assert "flex-wrap: wrap" in css
    assert "@media (max-width: 900px)" in css


def test_v3_onboarding_is_need_first_and_can_be_skipped() -> None:
    html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    for phrase in (
        "What do you need help with today?",
        "I was served or have a hearing",
        "Someone may be unsafe",
        "I need to understand an order",
        "I am not sure",
        "Skip and ask a question",
    ):
        assert phrase in html


def test_v3_versions_and_store_identity_are_consistent() -> None:
    from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, VERSION

    identity_local = json.loads((ROOT / "store" / "msix" / "identity.local.json").read_text(encoding="utf-8"))
    identity_example = json.loads((ROOT / "store" / "msix" / "identity.example.json").read_text(encoding="utf-8"))
    assert VERSION == "3.1.0"
    assert BUILD_NUMBER == 7
    assert PACKAGE_VERSION == "3.1.0.7"
    assert identity_local["package_version"] == PACKAGE_VERSION
    assert identity_example["package_version"] == PACKAGE_VERSION


def test_v3_launcher_quote_regression_and_local_asset_policy() -> None:
    vbs = (ROOT / "START_MAINE_FAMILY_LAW_LLM.vbs").read_text(encoding="utf-8")
    html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    assert "Chr(34)" in vbs
    assert 'fso.BuildPath(root, "START_MAINE_FAMILY_LAW_LLM.cmd")' in vbs
    assert 'src="/ui-assets/justice-facsimile.svg"' in html
    assert "http://" not in html
    assert html.count('href="https://focaf.jtforme.com/"') == 2
    assert html.count('href="https://focaf.jtforme.com/download-library/"') == 2
    assert 'target="_blank"' in html and 'rel="noreferrer noopener"' in html
