from __future__ import annotations

from typing import Any

from legal.conversation.glossary import Glossary
from legal.conversation.readability import ReadabilityAuditor


class PlainLanguageRewriter:
    def __init__(
        self,
        *,
        glossary: Glossary | None = None,
        readability: ReadabilityAuditor | None = None,
    ) -> None:
        self.glossary = glossary or Glossary()
        self.readability = readability or ReadabilityAuditor()

    def rewrite_response(self, response: dict[str, Any]) -> dict[str, Any]:
        explanation = str(response.get("explanation") or response.get("short_answer") or "")
        short = str(response.get("short_answer") or explanation)
        rewritten = short
        for term, definition in self.glossary.entries.items():
            if term in rewritten.lower():
                rewritten = rewritten.replace(term, f"{term} ({definition})")
                break
        what_this_means = rewritten
        what_this_does_not_mean = (
            "This does not mean the issue is resolved, filing-ready, or verified for current Maine law use."
        )
        text = (
            f"{rewritten}\n\nWhat this means: {what_this_means}\n\n"
            f"What this does not mean: {what_this_does_not_mean}\n\n"
            f"Review required: {response.get('review_required', True)}."
        )
        return {
            "text": text,
            "what_this_means": what_this_means,
            "what_this_does_not_mean": what_this_does_not_mean,
            "readability": self.readability.audit(text).as_dict(),
        }
