"""Prompt safety classification for legal-information-only operation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SafetyResult:
    category: str
    requires_citations: bool
    requires_disclaimer: bool
    requires_emergency_language: bool
    should_refuse_or_redirect: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "requires_citations": self.requires_citations,
            "requires_disclaimer": self.requires_disclaimer,
            "requires_emergency_language": self.requires_emergency_language,
            "should_refuse_or_redirect": self.should_refuse_or_redirect,
            "warnings": list(self.warnings),
        }


def classify_prompt(prompt: str) -> SafetyResult:
    text = prompt.lower().strip()
    if not text or text in {"hi", "hello", "hey", "thanks", "thank you"}:
        return SafetyResult("general", False, False, False, False)
    if any(term in text for term in ("immediate danger", "emergency", "911", "hurt me", "kill me")):
        return SafetyResult(
            "emergency_or_immediate_danger",
            True,
            True,
            True,
            True,
            ("route_to_emergency_resources",),
        )
    if any(term in text for term in ("domestic violence", "protection from abuse", "pfa", "restraining order", "abuse")):
        return SafetyResult(
            "domestic_violence_or_protection_from_abuse",
            True,
            True,
            True,
            True,
            ("use_safety_language", "official_resources_only"),
        )
    if any(term in text for term in ("child is unsafe", "child safety", "neglect", "abuse of my child", "danger to my child")):
        return SafetyResult("child_safety", True, True, True, True, ("child_safety_redirect",))
    if any(term in text for term in ("draft", "file", "filing", "form", "summons", "complaint", "motion")):
        return SafetyResult("form_or_filing", True, True, False, False, ("not_filing_ready",))
    if any(term in text for term in ("should i", "can i", "do i have to", "what should i do", "best strategy", "how do i")):
        return SafetyResult("legal_advice_request", True, True, False, False, ("provide_information_not_advice",))
    if any(term in text for term in ("statute", "rule", "court", "divorce", "parental rights", "child support", "modify", "family matter")):
        return SafetyResult("legal_information", True, True, False, False)
    if any(term in text for term in ("guarantee", "uncited", "without sources")):
        return SafetyResult("unsupported_without_sources", True, True, False, True, ("sources_required",))
    return SafetyResult("general", False, False, False, False)
