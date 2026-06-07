from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legal.conversation.legal_uncertainty import LegalUncertaintyGuard
from legal.conversation.next_steps import ConversationNextStepsBuilder
from legal.conversation.red_flag_presenter import RedFlagPresenter
from legal.conversation.review_status_presenter import ReviewStatusPresenter


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_answer_quality_rules.json"


class ConversationalAnswerBuilder:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.uncertainty = LegalUncertaintyGuard()
        self.next_steps = ConversationNextStepsBuilder()
        self.red_flags = RedFlagPresenter()
        self.review_status = ReviewStatusPresenter()

    def build(self, response: dict[str, Any]) -> dict[str, Any]:
        short_answer = str(response.get("short_answer") or response.get("explanation") or "Review-required status is available.")
        uncertainty = self.uncertainty.review(
            short_answer,
            source_freshness_status=str(response.get("source_freshness_status") or "source_unknown_freshness"),
            jurisdiction_scope=str(response.get("jurisdiction_scope") or "jurisdiction_unknown"),
        )
        source_cards = response.get("source_cards") or []
        citations = response.get("citations") or []
        missing = response.get("missing_information") or []
        red_flag_payload = self.red_flags.present(response.get("red_flags") or [])
        review_payload = self.review_status.present(response)
        sections = [
            {"section": "direct_answer_or_status", "value": uncertainty.text},
            {
                "section": "source_status",
                "value": {
                    "source_scope_status": response.get("source_scope_status"),
                    "source_freshness_status": response.get("source_freshness_status"),
                    "claim_support_status": response.get("claim_support_status"),
                },
            },
            {
                "section": "maine_authority_support",
                "value": {
                    "sources_used": source_cards,
                    "citations": citations,
                    "support_note": "Unsupported claims remain explicitly marked until verified.",
                },
            },
            {"section": "missing_or_unverified", "value": missing or ["No missing information reported by this deterministic check."]},
            {"section": "red_flags", "value": red_flag_payload},
            {
                "section": "plain_language_meaning",
                "value": response.get("plain_language_explanation") or response.get("explanation") or uncertainty.text,
            },
            {
                "section": "what_this_does_not_mean",
                "value": "This does not mean the output is legal advice, verified for current Maine law, or filing-ready.",
            },
            {"section": "review_and_filing_status", "value": review_payload},
            {"section": "next_steps", "value": self.next_steps.build(response)},
        ]
        text = "\n\n".join(f"{row['section']}: {row['value']}" for row in sections)
        clean = self.uncertainty.review(
            text,
            source_freshness_status=str(response.get("source_freshness_status") or "source_unknown_freshness"),
            jurisdiction_scope=str(response.get("jurisdiction_scope") or "jurisdiction_unknown"),
        )
        return {
            "schema": "maine_family_law_llm.conversational_answer_v2",
            "mode": response.get("mode"),
            "audience": response.get("audience"),
            "ordered_sections": sections,
            "text": clean.text,
            "warnings": list(dict.fromkeys([*uncertainty.warnings, *clean.warnings])),
            "review_required": review_payload["review_required"],
            "filing_ready_status": review_payload["filing_ready_status"],
        }
