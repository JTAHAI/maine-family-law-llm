from __future__ import annotations

from dataclasses import dataclass


BLOCKED_CERTAINTY = {
    "you will win": "the outcome cannot be predicted from this review-required output",
    "guaranteed": "not guaranteed",
    "definitely": "not certain from this review-required output",
    "file this as-is": "do not file this without the filing-ready gate and human review",
    "no attorney review needed": "human review remains required",
}


@dataclass(frozen=True)
class UncertaintyReview:
    text: str
    warnings: list[str]
    can_claim_current_law: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "warnings": self.warnings,
            "can_claim_current_law": self.can_claim_current_law,
        }


class LegalUncertaintyGuard:
    def review(
        self,
        text: str,
        *,
        source_freshness_status: str,
        jurisdiction_scope: str,
    ) -> UncertaintyReview:
        reviewed = text or ""
        warnings: list[str] = []
        for phrase, replacement in BLOCKED_CERTAINTY.items():
            if phrase in reviewed.lower():
                reviewed = reviewed.replace(phrase, replacement).replace(phrase.title(), replacement)
                warnings.append(f"blocked_certainty:{phrase}")
        can_claim_current = source_freshness_status == "source_verified" and jurisdiction_scope == "maine_only"
        if not can_claim_current and "current maine law" in reviewed.lower():
            reviewed = reviewed.replace("current Maine law", "Maine law after current-source verification")
            reviewed = reviewed.replace("Current Maine law", "Maine law after current-source verification")
            warnings.append("current_law_claim_blocked")
        return UncertaintyReview(reviewed, warnings, can_claim_current)
