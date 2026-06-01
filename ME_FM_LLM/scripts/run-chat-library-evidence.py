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
from maine_family_law_llm.chat_library import get_chat_library  # noqa: E402
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
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/external-evidence/chat_library_workbench_evidence.json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    html = render_local_workbench_html()
    rows = []
    blockers = []
    for question in SAMPLE_QUESTIONS:
        payload = ask(AskRequest(question=question, answer_style="checklist" if "gather" in question else "plain_language"))
        ok = bool(payload.get("grounded")) and bool(payload.get("citations")) and "not legal advice" in str(payload.get("answer", "")).lower()
        if not ok:
            blockers.append(f"sample_failed:{question}")
        rows.append(
            {
                "question": question,
                "grounded": payload.get("grounded"),
                "citation_count": len(payload.get("citations", [])),
                "failure_class": payload.get("failure_class"),
                "answer_preview": str(payload.get("answer", ""))[:360],
                "status": "pass" if ok else "failed",
            }
        )

    required_html = {
        "enter_to_submit": "event.key === 'Enter' && !event.shiftKey" in html,
        "json_error_handling": "non-JSON response" in html and "fetchJson" in html,
        "question_library": "/api/question-library" in html,
        "branding": "focaf.jtforme.com" in html,
        "transcript": "id=\"transcript\"" in html,
        "library_search": "id=\"library-search\"" in html,
        "served_papers_starter": "Served papers" in html,
    }
    blockers.extend([f"ui_missing:{key}" for key, value in required_html.items() if not value])

    library = get_chat_library()
    audiences = sorted({item.audience for item in library})
    for expected in ("parent", "lawyer", "caregiver", "counselor", "therapist"):
        if expected not in audiences:
            blockers.append(f"audience_missing:{expected}")
    if len(library) < 25:
        blockers.append("library_too_small_for_multi_audience_usability")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "chat_library_workbench_evidence_v1",
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "library_count": len(library),
        "audiences": audiences,
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
