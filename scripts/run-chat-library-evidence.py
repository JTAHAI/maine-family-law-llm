#!/usr/bin/env python3
"""Run local chat question-library evidence checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maine_family_law_llm.api import AskRequest, ask  # noqa: E402
from maine_family_law_llm.chat_library import get_chat_library, public_missing_information_prompts, public_prompt_packs, public_topics  # noqa: E402
from maine_family_law_llm.local_workbench_ui import render_local_workbench_html  # noqa: E402


SAMPLE_QUESTIONS = [
    "What are Maine's best-interest factors under 19-A M.R.S. § 1653?",
    "How do I use the best-interest factors in my parenting case?",
    "Can a therapist decide whether visits happen?",
    "What should I gather for child support?",
    "What if I need protection from abuse?",
    "How do I start a parental rights case in Maine?",
    "How do I check a proposed order for Rule 52 findings?",
    "I am a caregiver for a child. What should I ask the court about?",
    "I was served with family court papers. What should I do first?",
    "How do I organize evidence for family court?",
    "Can my child choose which parent to live with?",
    "Should I write a court letter for a parent?",
    "Can therapy records be used in family court?",
    "What should I do first in a Maine divorce?",
    "We were never married. How do parental rights work in Maine?",
    "How do I prepare for a temporary order hearing?",
    "Can I ask for supervised visits?",
    "How should I organize texts and app messages for court?",
    "My income changed. What should I gather for child support?",
    "Give me an intake checklist for a Maine parental rights case.",
    "How do I audit source cards before using an answer?",
    "What should a counselor do if subpoenaed in a family case?",
    "Can I paste session notes into this workbench?",
    "A child told me where they want to live. What should a therapist do?",
    "What should I ask a lawyer before filing a family case?",
    "What can I ask the court clerk about my family case?",
    "What if I cannot afford family court filing fees?",
    "How do I serve family court papers in Maine?",
    "What if we agree on a parenting plan?",
    "What if the other parent has substance use issues?",
    "What should I know if a GAL is involved?",
    "How should I organize school and medical records for family court?",
    "I was served with protection from abuse papers. What should I do first?",
    "Give me a checklist for opposing a Maine family motion.",
    "How should I review a parenting settlement before filing?",
    "What should I check for appeal preservation in a family case?",
    "A client asked me what to file in family court. What can I say?",
    "A parent wants me to testify in family court. What should I consider?",
    "A child resists contact with a parent. What should a therapist do?",
    "How do I share this answer with a lawyer for review?",
    "What information do I need before asking a family law question?",
    "How do I prepare for a case management conference in family court?",
    "How should I prepare for mediation in a Maine parenting case?",
    "I don't understand my parenting order. What should I check?",
    "What if I cannot follow the parenting order this weekend?",
    "What should I do if child support payments were missed?",
    "Build a missing information list for a new family case intake.",
    "How should I review a transcript from the local workbench?",
    "What documents should I ask a family-law client to send first?",
    "What should a caregiver ask a lawyer before filing anything?",
    "Can I enroll a child in school as a caregiver?",
    "Can I upload a child's school or medical records to this tool?",
    "A client wants legal strategy for family court. What can a counselor do?",
    "Can I write a treatment summary for family court?",
    "What if a court order about therapy is unclear?",
    "A parent asked me for a custody opinion letter. What should I do?",
    "How do I export a reviewer handoff from this chat?",
]


def _style_for_question(question: str) -> str:
    lower_question = question.lower()
    style = "checklist" if any(
        term in lower_question
        for term in (
            "gather",
            "checklist",
            "prepare",
            "organize",
            "serve",
            "afford",
            "agree",
            "gal",
            "appeal",
            "support",
        )
    ) else "plain_language"
    if any(
        term in lower_question
        for term in ("subpoena", "session notes", "what to file", "testify", "therapist", "counselor")
    ):
        style = "professional_boundary"
    if any(term in lower_question for term in ("source cards", "settlement")):
        style = "source_card_table"
    if any(term in lower_question for term in ("ask a lawyer", "court clerk", "guardianship or a parental rights")):
        style = "questions_to_ask"
    if any(term in lower_question for term in ("missing information", "what information", "transcript", "reviewer handoff", "don't understand", "cannot follow", "enroll a child", "upload a child's", "case management", "mediation")):
        style = "missing_information"
    return style


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/external-evidence/chat_library_workbench_evidence.json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    html = render_local_workbench_html()
    rows = []
    blockers = []
    for question in SAMPLE_QUESTIONS:
        style = _style_for_question(question)
        payload = ask(AskRequest(question=question, answer_style=style))
        ok = (
            bool(payload.get("grounded"))
            and bool(payload.get("citations"))
            and "not legal advice" in str(payload.get("answer", "")).lower()
            and bool(payload.get("review_required", True))
            and bool(
                payload.get("metadata", {}).get("matched_library_id")
                or "best-interest" in str(payload.get("answer", "")).lower()
            )
        )
        if not ok:
            blockers.append(f"sample_failed:{question}")
        rows.append(
            {
                "question": question,
                "answer_style": style,
                "grounded": payload.get("grounded"),
                "citation_count": len(payload.get("citations", [])),
                "failure_class": payload.get("failure_class"),
                "source_card_count": payload.get("source_card_count"),
                "review_required": payload.get("review_required"),
                "matched_library_id": payload.get("metadata", {}).get("matched_library_id"),
                "answer_preview": str(payload.get("answer", ""))[:360],
                "status": "pass" if ok else "failed",
            }
        )

    required_html = {
        "enter_to_submit": "event.key === 'Enter' && !event.shiftKey" in html,
        "json_error_handling": "non-JSON response" in html and "fetchJson" in html,
        "question_library": "/api/question-library" in html,
        "topic_endpoint": "/api/question-topics" in html,
        "starter_prompt_packs": "/api/starter-prompt-packs" in html and "renderPromptPacks" in html,
        "missing_information_endpoint": "/api/missing-information-prompts" in html,
        "missing_information_style": "missing_information" in html and "handoff-panel" in html and "renderHandoff" in html,
        "questions_to_ask_style": "questions_to_ask" in html,
        "branding": "focaf.jtforme.com" in html,
        "transcript": "id=\"transcript\"" in html,
        "json_transcript_export": "local_chat_transcript_v2" in html and "id=\"download-json-button\"" in html,
        "library_search": "id=\"library-search\"" in html,
        "topic_filter": "id=\"topic-filter\"" in html and "populateTopicFilter" in html,
        "quick_topic_search": "id=\"library-topic-search\"" in html,
        "source_card_copy": "data-copy-source" in html,
        "source_inspector": "data-inspect-source" in html and "id=\"source-inspector\"" in html,
        "source_rich_export": "Latest source cards:" in html and "Latest payload metadata:" in html,
        "served_papers_starter": "Served papers" in html,
    }
    blockers.extend([f"ui_missing:{key}" for key, value in required_html.items() if not value])

    library = get_chat_library()
    audiences = sorted({item.audience for item in library})
    for expected in ("parent", "lawyer", "caregiver", "counselor", "therapist"):
        if expected not in audiences:
            blockers.append(f"audience_missing:{expected}")
    if len(library) < 104:
        blockers.append("library_too_small_for_v182_multi_audience_usability")
    topics = public_topics()
    topic_names = sorted(row["topic"] for row in topics)
    for expected_topic in (
        "divorce",
        "parental_rights",
        "child_support",
        "professional_boundaries",
        "intake_triage",
        "authority_matrix",
        "questions_to_ask",
        "draft_review",
        "local_workbench_use",
        "missing_information",
        "order_review",
    ):
        if expected_topic not in topic_names:
            blockers.append(f"topic_missing:{expected_topic}")

    prompt_packs = public_prompt_packs()
    missing_prompts = public_missing_information_prompts()
    if len(missing_prompts) < len(library):
        blockers.append("missing_information_prompt_rows_missing")
    if not any(row.get("follow_up_questions") for row in missing_prompts):
        blockers.append("follow_up_questions_missing")
    if len(prompt_packs) < 7:
        blockers.append("starter_prompt_packs_missing")
    for expected_audience in ("parent", "lawyer", "caregiver", "counselor", "therapist"):
        if not any(pack.get("audience") == expected_audience for pack in prompt_packs):
            blockers.append(f"starter_pack_audience_missing:{expected_audience}")
    if any(pack.get("prompt_count", 0) < 5 for pack in prompt_packs):
        blockers.append("starter_pack_prompt_count_too_small")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "chat_library_workbench_evidence_v3",
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "library_count": len(library),
        "audiences": audiences,
        "topic_count": len(topics),
        "topics": topic_names,
        "starter_prompt_pack_count": len(prompt_packs),
        "starter_prompt_packs": [pack["id"] for pack in prompt_packs],
        "missing_information_prompt_count": len(missing_prompts),
        "ui_checks": required_html,
        "sample_results": rows,
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1 if args.require_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
