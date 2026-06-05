from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from legal.product.family_justice_workbench_v205 import (
    PACKET_SCHEMA,
    VERSION,
    build_workbench_packet,
    render_workbench_html,
    write_evidence_outputs,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v205_packet_is_source_card_first_review_required_and_blocked() -> None:
    packet = build_workbench_packet(
        "I was served with family court papers and need to know my next step.",
        audience="parent",
        posture="initial_complaint",
        requested_output_style="checklist",
    )

    assert packet["schema"] == PACKET_SCHEMA
    assert packet["version"] == VERSION
    assert packet["source_cards"]
    assert packet["filing_readiness_status"]["review_required"] is True
    assert packet["filing_readiness_status"]["filing_ready"] is False
    assert packet["why_not_filing_ready"]
    assert "served_with_family_court_papers" in packet["issue_labels"]


def test_v205_does_not_emit_current_law_certainty_without_freshness() -> None:
    packet = build_workbench_packet("What are Maine best-interest factors for parental rights?")

    assert packet["claims"]["current_law_certified"] is False
    assert all(card["can_support_current_law_claim"] is False for card in packet["source_cards"])
    assert all(card["freshness_status"] == "must_verify_current_official_source" for card in packet["source_cards"])
    assert "current law says" not in packet["plain_language_answer"].lower()


def test_v205_professional_boundary_for_therapist_avoids_legal_strategy() -> None:
    packet = build_workbench_packet(
        "A parent asked me as a therapist what to file and whether I can share session notes.",
        audience="therapist",
        requested_output_style="professional_boundary",
    )

    answer = packet["plain_language_answer"].lower()
    assert "professional-boundary answer" in answer
    assert "not legal strategy" in answer
    assert "what relief to request" in answer
    assert "court_clerk_lawyer_boundary" in packet["issue_labels"]
    assert "school_medical_records_privacy" in packet["issue_labels"]


def test_v205_pfa_and_safety_routes_to_emergency_caveat() -> None:
    packet = build_workbench_packet(
        "I need protection from abuse and I am unsafe tonight during child exchanges.",
        audience="parent",
    )

    routing = packet["urgency_safety_routing"]
    assert routing["safety_routing"] is True
    assert routing["urgency"] == "safety_priority"
    assert "911" in routing["emergency_caveat"]
    assert "protection_from_abuse_safety" in packet["issue_labels"]


def test_v205_appeal_questions_do_not_route_to_generic_parenting() -> None:
    packet = build_workbench_packet(
        "How long do I have to appeal a Maine parenting order and what transcript facts matter?",
        audience="lawyer",
        posture="appeal",
    )

    assert packet["issue_labels"][0] == "appeal_deadline_preservation_transcript"
    assert "parental_rights_responsibilities" not in packet["issue_labels"]
    assert any(card["source_id"] == "starter_me_appellate_rules" for card in packet["source_cards"])


def test_v205_rule52_best_interest_and_non_delegation_red_flags() -> None:
    packet = build_workbench_packet(
        "The final order has no Rule 52 findings, skips best-interest factors, and says the therapist decides when visits happen.",
        audience="reviewer",
        posture="final_order",
        requested_output_style="reviewer_handoff",
    )

    red_flags = {flag["label"] for flag in packet["red_flags"]}
    assert "Missing Rule 52 findings" in red_flags
    assert "Best-interest factor gap" in red_flags
    assert "Therapist/GAL/non-delegation contact red flag" in red_flags
    assert "Contact restriction without sourced findings" in red_flags


def test_v205_caregiver_records_privacy_route_is_explicit() -> None:
    packet = build_workbench_packet(
        "I am a caregiver. Can I enroll a child and access school records and medical records?",
        audience="caregiver",
        requested_output_style="missing_information",
    )

    assert "caregiver_guardianship_grandparent" in packet["issue_labels"]
    assert "school_medical_records_privacy" in packet["issue_labels"]
    assert any(card["source_id"] == "starter_me_records_privacy" for card in packet["source_cards"])
    assert packet["export_metadata"]["private_matter_data_included"] is False


def test_v205_html_evidence_contains_expected_ui_markers() -> None:
    html = render_workbench_html()

    for marker in (
        "Family Justice Workbench",
        "ask-section",
        "review-section",
        "next-steps-section",
        "source-card",
        "blocker-card",
        "red-flag-chip",
        "role-pathway",
        "authority-matrix-preview",
        "review_required=true",
        "filing_ready=false",
        "focaf-family-law-llm-horizontal.svg",
    ):
        assert marker in html
    assert "join('\\n" not in html
    assert "].join('\\n" not in html


def test_v205_evidence_outputs_are_valid_json_and_schema_stable(tmp_path: Path) -> None:
    outputs = write_evidence_outputs(tmp_path)

    packet_payload = json.loads(Path(outputs["packet"]).read_text(encoding="utf-8"))
    audit = json.loads(Path(outputs["audit"]).read_text(encoding="utf-8"))
    summary = json.loads(Path(outputs["test_summary"]).read_text(encoding="utf-8"))
    html = Path(outputs["html"]).read_text(encoding="utf-8")

    assert packet_payload["schema"] == PACKET_SCHEMA
    assert packet_payload["version"] == VERSION
    assert packet_payload["packets"]
    assert audit["status"] == "pass"
    assert summary["status"] == "pass"
    first = packet_payload["packets"][0]
    for key in (
        "answer_preview",
        "plain_language_answer",
        "issue_labels",
        "source_cards",
        "filing_readiness_status",
        "reviewer_handoff",
        "export_metadata",
    ):
        assert key in first
    assert "Family Justice Workbench" in html


def test_v205_evidence_script_generates_required_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-family-justice-workbench-evidence.py",
            "--output-dir",
            str(tmp_path),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert set(payload["outputs"]) == {"packet", "audit", "html", "test_summary"}


def test_v205_api_endpoint_returns_packet_when_fastapi_available() -> None:
    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    payload = api.family_justice_workbench(
        api.FamilyJusticeWorkbenchRequest(
            question="What should a reviewer check before filing a Maine family motion?",
            audience="reviewer",
            requested_output_style="reviewer_handoff",
        )
    )

    assert payload["schema"] == PACKET_SCHEMA
    assert payload["filing_readiness_status"]["review_required"] is True
    assert payload["filing_readiness_status"]["filing_ready"] is False


def test_v205_local_release_zip_helper_excludes_private_runtime_artifacts() -> None:
    script = (ROOT / "scripts" / "create-local-release-zip.ps1").read_text(encoding="utf-8")

    for marker in (
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".mfl_work",
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "eval_store",
        ".env.*",
        "*.sqlite3",
        "*.safetensors",
    ):
        assert marker in script
    assert "Compress-Archive" in script
