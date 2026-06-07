from __future__ import annotations

from typing import Any

from legal.conversation.draft_blockers import DraftBlockerDetector
from legal.conversation.draft_intake import DraftIntakeAnalyzer
from legal.conversation.draft_review_checklist import DraftReviewChecklistBuilder


class DraftingConversation:
    def __init__(self) -> None:
        self.intake = DraftIntakeAnalyzer()
        self.blockers = DraftBlockerDetector()
        self.checklist = DraftReviewChecklistBuilder()

    def prepare(self, *, draft_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        intake = self.intake.analyze(draft_type, payload)
        blockers = self.blockers.detect(draft_type=draft_type, payload=payload, intake=intake)
        placeholders = []
        if not payload.get("citations"):
            placeholders.append(
                {
                    "label": "citation_placeholder",
                    "text": "[PLACEHOLDER - verified Maine citation required]",
                    "is_real_citation": False,
                }
            )
        return {
            "schema": "maine_family_law_llm.drafting_conversation_v2",
            "draft_type": draft_type,
            "intake": intake,
            "blockers": blockers,
            "review_required": True,
            "filing_ready_status": "blocked_from_filing_ready",
            "citation_placeholders": placeholders,
            "user_fact_policy": "User-provided facts remain user_provided unless evidence-mapped.",
            "draft_must_not_create": ["facts", "legal authority", "verified citations"],
            "why_not_filing_ready": blockers or ["human_review_missing", "filing_ready_gate_not_run"],
            "review_checklist": self.checklist.build(draft_type=draft_type, blockers=blockers),
        }
