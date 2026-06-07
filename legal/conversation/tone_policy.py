from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_tone_policy.json"


@dataclass(frozen=True)
class ToneRewrite:
    pattern: str
    category: str
    replacement: str


@dataclass
class ToneReviewResult:
    text: str
    warnings: list[str] = field(default_factory=list)
    rewrites: list[dict[str, str]] = field(default_factory=list)
    escalation_messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "warnings": self.warnings,
            "rewrites": self.rewrites,
            "escalation_messages": self.escalation_messages,
        }


class TonePolicy:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.rewrites = [
            ToneRewrite(
                pattern=str(item["pattern"]),
                category=str(item["category"]),
                replacement=str(item["replacement"]),
            )
            for item in self.config.get("blocked_phrases", [])
        ]

    def apply(
        self,
        text: str,
        *,
        source_freshness_status: str = "source_unknown_freshness",
        jurisdiction_scope: str = "jurisdiction_unknown",
        filing_ready_passed: bool = False,
    ) -> ToneReviewResult:
        reviewed = text or ""
        warnings: list[str] = []
        rewrites: list[dict[str, str]] = []
        for rewrite in self.rewrites:
            if rewrite.pattern.lower() not in reviewed.lower():
                continue
            if rewrite.category == "filing_ready_claim" and filing_ready_passed:
                continue
            start_text = reviewed
            reviewed = reviewed.replace(rewrite.pattern, rewrite.replacement)
            reviewed = reviewed.replace(rewrite.pattern.title(), rewrite.replacement)
            if reviewed != start_text:
                rewrites.append(
                    {
                        "pattern": rewrite.pattern,
                        "category": rewrite.category,
                        "replacement": rewrite.replacement,
                    }
                )
                warnings.append(f"tone_rewrite:{rewrite.category}")
        if source_freshness_status != "source_verified":
            message = (self.config.get("freshness_messages") or {}).get(source_freshness_status)
            if message:
                warnings.append(str(message))
        jurisdiction_message = (self.config.get("jurisdiction_messages") or {}).get(jurisdiction_scope)
        if jurisdiction_message:
            warnings.append(str(jurisdiction_message))
        escalation_messages = self.escalation_messages(reviewed)
        return ToneReviewResult(
            text=reviewed,
            warnings=warnings,
            rewrites=rewrites,
            escalation_messages=escalation_messages,
        )

    def escalation_messages(self, text: str) -> list[str]:
        low = (text or "").lower()
        messages: list[str] = []
        for row in self.config.get("escalation_triggers", []):
            if any(keyword in low for keyword in row.get("keywords", [])):
                messages.append(str(row.get("message") or ""))
        return messages

    def review_required_phrase(self) -> str:
        return str(self.config.get("review_required_phrase") or "Review required.")

    def insufficient_source_phrase(self) -> str:
        return str(self.config.get("insufficient_source_phrase") or "")

    def filing_ready_blocked_phrase(self) -> str:
        return str(self.config.get("filing_ready_blocked_phrase") or "")
