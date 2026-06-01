from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BEST_INTEREST_FACTORS = {
    "child_age": ("age of the child", "child's age", "developmental"),
    "parent_relationship": ("relationship with each parent", "parent-child relationship"),
    "preference": ("child's preference", "preference of the child"),
    "stability": ("stability", "stable living", "continuity"),
    "school_community": ("school", "community", "education"),
    "sibling_relationships": ("sibling", "brother", "sister"),
    "cooperation": ("cooperate", "communication between the parents", "encourage contact"),
    "domestic_abuse": ("domestic abuse", "protection from abuse", "pfa"),
    "safety": ("safety", "risk of harm", "supervised contact"),
    "medical_needs": ("medical", "therapy", "counseling", "health"),
    "special_needs": ("special needs", "disability", "accommodation"),
    "history_of_care": ("primary caregiver", "history of care", "caretaking"),
    "parent_capacity": ("capacity to parent", "ability to parent", "fitness"),
    "substance_use": ("substance", "alcohol", "drug"),
    "family_support": ("extended family", "grandparent", "family support"),
    "other_relevant": ("other relevant", "totality", "all relevant factors"),
}

CONTACT_RESTRICTION_TERMS = (
    "supervised contact",
    "supervised visitation",
    "no contact",
    "suspended contact",
    "restricted contact",
    "therapeutic visitation",
)
EVIDENCE_SUPPORT_TERMS = (
    "because",
    "the court finds",
    "evidence showed",
    "testimony",
    "exhibit",
    "credible",
    "risk",
    "safety",
    "harm",
)


@dataclass(frozen=True)
class FindingsReviewReport:
    status: str
    factor_coverage: dict[str, bool] = field(default_factory=dict)
    missing_best_interest_factors: tuple[str, ...] = ()
    missing_findings: tuple[str, ...] = ()
    contact_restriction_report: dict[str, Any] = field(default_factory=dict)
    pfa_family_overlap_warning: str | None = None
    red_flags: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    proposed_findings_checklist: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "factor_coverage": self.factor_coverage,
            "missing_best_interest_factors": list(self.missing_best_interest_factors),
            "missing_findings": list(self.missing_findings),
            "contact_restriction_report": self.contact_restriction_report,
            "pfa_family_overlap_warning": self.pfa_family_overlap_warning,
            "red_flags": list(self.red_flags),
            "blockers": list(self.blockers),
            "proposed_findings_checklist": list(self.proposed_findings_checklist),
        }


class Rule52BestInterestFindingsEngine:
    """Deterministic review of proposed family-law findings/orders.

    The engine does not decide legal sufficiency. It identifies missing structured
    findings and creates review blockers that an attorney must clear.
    """

    def review_order(self, text: str, *, posture: str = "final_order") -> FindingsReviewReport:
        lowered = text.lower()
        coverage = self.best_interest_factor_coverage(text)
        missing = tuple(factor for factor, covered in coverage.items() if not covered)
        missing_findings = []
        if posture in {"final_order", "post_judgment", "remand"} and not self._has_findings_section(lowered):
            missing_findings.append("findings_of_fact_section_missing")
        if "parental rights" in lowered or "primary residence" in lowered or "contact" in lowered:
            if len(missing) > 8:
                missing_findings.append("best_interest_analysis_too_sparse")
        contact_report = self.contact_restriction_support(text)
        pfa_warning = self.pfa_independent_analysis_warning(text)
        red_flags = []
        blockers = []
        if missing_findings:
            red_flags.append("missing Rule 52 findings")
            blockers.extend(f"rule52:{item}" for item in missing_findings)
        if missing:
            red_flags.append("unsupported best-interest findings")
        if contact_report["restriction_detected"] and not contact_report["support_detected"]:
            red_flags.append("contact restriction without sourced findings")
            blockers.append("contact_restriction_without_supported_findings")
        if pfa_warning:
            red_flags.append("PFA-to-family-case independent-analysis warning")
            blockers.append("pfa_family_overlap_independent_analysis_missing")
        checklist = self.proposed_findings_checklist()
        return FindingsReviewReport(
            status="pass",
            factor_coverage=coverage,
            missing_best_interest_factors=missing,
            missing_findings=tuple(missing_findings),
            contact_restriction_report=contact_report,
            pfa_family_overlap_warning=pfa_warning,
            red_flags=tuple(sorted(set(red_flags))),
            blockers=tuple(sorted(set(blockers))),
            proposed_findings_checklist=tuple(checklist),
        )

    def best_interest_factor_coverage(self, text: str) -> dict[str, bool]:
        lowered = text.lower()
        return {
            factor: any(term in lowered for term in terms)
            for factor, terms in BEST_INTEREST_FACTORS.items()
        }

    def proposed_findings_checklist(self) -> list[str]:
        return [
            "Identify posture, requested relief, and governing Maine family-law authority.",
            "Make express findings of fact tied to record evidence for each contested issue.",
            "Address best-interest factors that are material to parental rights, residence, and contact.",
            "Explain any restriction on parent-child contact with evidence and safety findings.",
            "Do not delegate contact/residence decisions to GAL, therapist, or third party.",
            "If PFA facts overlap, make an independent family-case analysis rather than importing findings.",
            "Tie every factual finding to testimony, exhibit, stipulation, or admitted document.",
        ]

    def contact_restriction_support(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        detected_terms = [term for term in CONTACT_RESTRICTION_TERMS if term in lowered]
        support_detected = False
        support_terms: list[str] = []
        if detected_terms:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sentence in sentences:
                s_lower = sentence.lower()
                if any(term in s_lower for term in CONTACT_RESTRICTION_TERMS):
                    terms = [term for term in EVIDENCE_SUPPORT_TERMS if term in s_lower]
                    if terms:
                        support_detected = True
                        support_terms.extend(terms)
        return {
            "restriction_detected": bool(detected_terms),
            "restriction_terms": detected_terms,
            "support_detected": support_detected,
            "support_terms": sorted(set(support_terms)),
        }

    def pfa_independent_analysis_warning(self, text: str) -> str | None:
        lowered = text.lower()
        has_pfa = "protection from abuse" in lowered or "pfa" in lowered
        affects_family = any(term in lowered for term in ("parental rights", "primary residence", "contact", "custody"))
        has_independent = "independent analysis" in lowered or "independently finds" in lowered
        if has_pfa and affects_family and not has_independent:
            return "PFA facts are used in a family-law contact/residence context without an express independent family-case analysis."
        return None

    def _has_findings_section(self, lowered: str) -> bool:
        return any(
            phrase in lowered
            for phrase in ("findings of fact", "the court finds", "finds as follows", "factual findings")
        )
