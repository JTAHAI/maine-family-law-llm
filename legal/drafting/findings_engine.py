from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

BEST_INTEREST_FACTORS = {
    "child_age": ("age of the child", "child's age", "developmental", "age and developmental", "years old"),
    "parent_relationship": ("relationship with each parent", "parent-child relationship", "bond with"),
    "preference": ("child's preference", "preference of the child", "wishes of the child"),
    "stability": ("stability", "stable living", "continuity", "continuity of care"),
    "school_community": ("school", "community", "education"),
    "sibling_relationships": ("sibling", "brother", "sister"),
    "cooperation": ("cooperate", "communication between the parents", "encourage contact", "facilitate contact"),
    "domestic_abuse": ("domestic abuse", "protection from abuse", "pfa"),
    "safety": ("safety", "risk of harm", "supervised contact", "protective factor"),
    "medical_needs": ("medical", "therapy", "counseling", "health"),
    "special_needs": ("special needs", "disability", "accommodation"),
    "history_of_care": ("primary caregiver", "history of care", "caretaking"),
    "parent_capacity": ("capacity to parent", "ability to parent", "fitness", "parenting capacity"),
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
THIRD_PARTY_DELEGATION_TERMS = (
    "as determined by the therapist",
    "therapist shall determine",
    "guardian ad litem shall determine",
    "gal shall determine",
    "at the discretion of the therapist",
    "at the discretion of the guardian ad litem",
)
_SENTENCE_RE = re.compile(r"[^\n.!?]+(?:[.!?]+|$)", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "were", "with"}


@dataclass(frozen=True)
class FindingsReviewReport:
    status: str
    factor_coverage: dict[str, bool] = field(default_factory=dict)
    factor_matrix: tuple[dict[str, Any], ...] = ()
    missing_best_interest_factors: tuple[str, ...] = ()
    missing_findings: tuple[str, ...] = ()
    contact_restriction_report: dict[str, Any] = field(default_factory=dict)
    delegation_report: dict[str, Any] = field(default_factory=dict)
    pfa_family_overlap_warning: str | None = None
    red_flags: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    proposed_findings_checklist: tuple[str, ...] = ()
    review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "maine_findings_review_v2",
            "status": self.status,
            "factor_coverage": self.factor_coverage,
            "factor_matrix": list(self.factor_matrix),
            "missing_best_interest_factors": list(self.missing_best_interest_factors),
            "missing_findings": list(self.missing_findings),
            "contact_restriction_report": self.contact_restriction_report,
            "delegation_report": self.delegation_report,
            "pfa_family_overlap_warning": self.pfa_family_overlap_warning,
            "red_flags": list(self.red_flags),
            "blockers": list(self.blockers),
            "proposed_findings_checklist": list(self.proposed_findings_checklist),
            "review_required": self.review_required,
        }


class Rule52BestInterestFindingsEngine:
    """Deterministic review of proposed family-law findings/orders.

    The engine identifies text and record spans for review. It never decides
    legal sufficiency, credibility, best interests, or whether a restriction is
    warranted.
    """

    def review_order(
        self,
        text: str,
        *,
        posture: str = "final_order",
        evidence_records: Iterable[dict[str, Any]] | None = None,
    ) -> FindingsReviewReport:
        safe_text = str(text or "").replace("\x00", "")[:1_500_000]
        lowered = safe_text.lower()
        matrix = self.best_interest_factor_matrix(safe_text, evidence_records=evidence_records)
        coverage = {row["factor_id"]: row["status"] == "addressed" for row in matrix}
        missing = tuple(row["factor_id"] for row in matrix if row["status"] != "addressed")
        family_decision = any(term in lowered for term in ("parental rights", "primary residence", "custody", "best interest", "contact schedule", "parent-child contact", "supervised contact", "no contact", "visitation"))
        findings_posture = posture in {"final_order", "post_judgment", "remand", "proposed_order"}

        missing_findings: list[str] = []
        if findings_posture and not self._has_findings_section(lowered):
            missing_findings.append("findings_of_fact_section_missing")
        if family_decision and len(missing) > 8:
            missing_findings.append("best_interest_analysis_too_sparse")

        contact_report = self.contact_restriction_support(safe_text, evidence_records=evidence_records)
        delegation_report = self.third_party_delegation_review(safe_text)
        pfa_warning = self.pfa_independent_analysis_warning(safe_text)
        red_flags: list[str] = []
        blockers: list[str] = []
        if missing_findings:
            red_flags.append("missing Rule 52 findings")
            blockers.extend(f"rule52:{item}" for item in missing_findings)
        if family_decision and missing:
            red_flags.append("best-interest factors require review")
            blockers.extend(f"best_interest_factor_missing:{factor}" for factor in missing)
        if contact_report["restriction_detected"] and not contact_report["support_detected"]:
            red_flags.append("contact restriction without sourced findings")
            blockers.append("contact_restriction_without_supported_findings")
        if delegation_report["delegation_detected"]:
            red_flags.append("third-party decision delegation requires review")
            blockers.append("third_party_parenting_decision_delegation")
        if pfa_warning:
            red_flags.append("PFA-to-family-case independent-analysis warning")
            blockers.append("pfa_family_overlap_independent_analysis_missing")
        status = "checked" if not blockers else "review_required"
        return FindingsReviewReport(
            status=status,
            factor_coverage=coverage,
            factor_matrix=tuple(matrix),
            missing_best_interest_factors=missing,
            missing_findings=tuple(missing_findings),
            contact_restriction_report=contact_report,
            delegation_report=delegation_report,
            pfa_family_overlap_warning=pfa_warning,
            red_flags=tuple(sorted(set(red_flags))),
            blockers=tuple(sorted(set(blockers))),
            proposed_findings_checklist=tuple(self.proposed_findings_checklist()),
        )

    def best_interest_factor_coverage(self, text: str) -> dict[str, bool]:
        return {row["factor_id"]: row["status"] == "addressed" for row in self.best_interest_factor_matrix(text)}

    def best_interest_factor_matrix(
        self,
        text: str,
        *,
        evidence_records: Iterable[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        sentences = list(self._sentences(text))
        records = self._safe_records(evidence_records)
        rows: list[dict[str, Any]] = []
        for factor, terms in BEST_INTEREST_FACTORS.items():
            draft_spans = []
            for sentence, start, end in sentences:
                matched = [term for term in terms if term in sentence.lower()]
                if matched:
                    draft_spans.append({"start_offset": start, "end_offset": end, "text": sentence, "matched_terms": matched})
            record_spans = self._record_matches(terms, records)
            rows.append({
                "factor_id": factor,
                "label": factor.replace("_", " "),
                "status": "addressed" if draft_spans else "missing",
                "draft_spans": draft_spans[:10],
                "supporting_record_spans": record_spans[:10],
                "record_support_status": "candidate_spans_found" if record_spans else "no_candidate_span_found",
                "review_required": True,
                "does_not_prove": "A text match does not establish that the factor was legally sufficient, credible, or correctly weighed.",
            })
        return rows

    def proposed_findings_checklist(self) -> list[str]:
        return [
            "Identify posture, requested relief, and governing Maine family-law authority.",
            "Make express findings of fact tied to record evidence for each contested issue.",
            "Address every best-interest factor material to parental rights, residence, and contact.",
            "Explain any restriction on parent-child contact with exact evidence and safety findings.",
            "Do not delegate contact or residence decisions to a GAL, therapist, or another third party.",
            "If PFA facts overlap, make an independent family-case analysis rather than importing findings.",
            "Tie every factual finding to testimony, exhibit, stipulation, or admitted document.",
            "State how materially conflicting evidence was resolved or why it was not material.",
        ]

    def contact_restriction_support(
        self,
        text: str,
        *,
        evidence_records: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        detected_terms: list[str] = []
        restriction_spans: list[dict[str, Any]] = []
        support_spans: list[dict[str, Any]] = []
        sentences = list(self._sentences(text))
        for index, (sentence, start, end) in enumerate(sentences):
            s_lower = sentence.lower()
            terms = [term for term in CONTACT_RESTRICTION_TERMS if term in s_lower]
            if not terms:
                continue
            detected_terms.extend(terms)
            restriction_spans.append({"start_offset": start, "end_offset": end, "text": sentence, "terms": terms})
            window = sentences[index:index + 2]
            joined = " ".join(item[0] for item in window).lower()
            supports = [term for term in EVIDENCE_SUPPORT_TERMS if term in joined]
            if supports:
                support_spans.append({"start_offset": start, "end_offset": window[-1][2], "text": " ".join(item[0] for item in window), "terms": supports})
        evidence_candidates = self._record_matches(
            (*CONTACT_RESTRICTION_TERMS, "risk", "harm", "safety", "supervised"),
            self._safe_records(evidence_records),
        )
        return {
            "restriction_detected": bool(detected_terms),
            "restriction_terms": sorted(set(detected_terms)),
            "restriction_spans": restriction_spans[:20],
            "support_detected": bool(support_spans),
            "support_terms": sorted({term for span in support_spans for term in span["terms"]}),
            "support_spans": support_spans[:20],
            "candidate_record_spans": evidence_candidates[:20],
            "review_required": bool(detected_terms),
        }

    def third_party_delegation_review(self, text: str) -> dict[str, Any]:
        rows = []
        for sentence, start, end in self._sentences(text):
            terms = [term for term in THIRD_PARTY_DELEGATION_TERMS if term in sentence.lower()]
            if terms:
                rows.append({"start_offset": start, "end_offset": end, "text": sentence, "matched_terms": terms})
        return {"delegation_detected": bool(rows), "spans": rows[:20], "review_required": bool(rows)}

    def pfa_independent_analysis_warning(self, text: str) -> str | None:
        lowered = text.lower()
        has_pfa = "protection from abuse" in lowered or re.search(r"\bpfa\b", lowered) is not None
        affects_family = any(term in lowered for term in ("parental rights", "primary residence", "contact", "custody"))
        has_independent = "independent analysis" in lowered or "independently finds" in lowered or "independent family-case" in lowered
        if has_pfa and affects_family and not has_independent:
            return "PFA facts are used in a family-law contact/residence context without an express independent family-case analysis."
        return None

    def _record_matches(self, terms: Iterable[str], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        term_tokens = {token for term in terms for token in self._tokens(term)}
        matches: list[dict[str, Any]] = []
        for record in records:
            for sentence, start, end in self._sentences(record["text"]):
                tokens = self._tokens(sentence)
                overlap = len(term_tokens & tokens) / max(len(term_tokens), 1)
                exact = [term for term in terms if term in sentence.lower()]
                if not exact and overlap < 0.28:
                    continue
                matches.append({
                    "evidence_id": record["evidence_id"],
                    "safe_locator": record["safe_locator"],
                    "page_number": record["page_number"],
                    "source_hash": record["source_hash"],
                    "start_offset": start,
                    "end_offset": end,
                    "text": sentence[:800],
                    "match_type": "exact_term" if exact else "lexical_candidate",
                    "confidence": 1.0 if exact else round(overlap, 3),
                })
        matches.sort(key=lambda row: (-float(row["confidence"]), row["evidence_id"], row["start_offset"]))
        return matches

    def _safe_records(self, records: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
        output = []
        for raw in list(records or [])[:10_000]:
            if not isinstance(raw, dict):
                continue
            evidence_id = str(raw.get("evidence_id") or raw.get("source_id") or "")[:256]
            text = next((str(raw.get(key) or "") for key in ("text", "derived_text", "content", "text_excerpt", "snippet") if str(raw.get(key) or "").strip()), "")
            if not evidence_id or not text:
                continue
            locator = str(raw.get("source_locator") or raw.get("source_path") or raw.get("filename") or raw.get("title") or evidence_id)
            safe_locator = re.split(r"[\\/]", locator)[-1][:240]
            source_hash = str(raw.get("source_hash") or raw.get("sha256") or "").lower()
            if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
                source_hash = ""
            output.append({
                "evidence_id": evidence_id,
                "safe_locator": safe_locator,
                "page_number": max(0, int(raw.get("page_number") or 0)),
                "source_hash": source_hash,
                "text": text.replace("\x00", "")[:500_000],
            })
        return output

    @staticmethod
    def _sentences(text: str):
        for match in _SENTENCE_RE.finditer(text):
            sentence = " ".join(match.group(0).split())
            if sentence:
                yield sentence, match.start(), match.end()

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS and len(token) > 1}

    @staticmethod
    def _has_findings_section(lowered: str) -> bool:
        return any(phrase in lowered for phrase in ("findings of fact", "the court finds", "finds as follows", "factual findings"))
