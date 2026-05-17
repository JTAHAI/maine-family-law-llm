from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

Disposition = Literal["affirmed", "vacated", "remanded", "reversed", "dismissed", "mixed", "unknown"]
ReviewStandard = Literal["abuse_of_discretion", "clear_error", "de_novo", "mixed", "unknown"]


@dataclass(frozen=True)
class LawCourtCaseBrief:
    source_id: str
    citation: str | None
    procedural_posture: str
    standard_of_review: ReviewStandard
    disposition: Disposition
    holding: str | None
    issue_labels: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()
    extracted_signals: dict[str, bool] = field(default_factory=dict)
    caption: str | None = None
    docket_number: str | None = None
    decision_date: str | None = None
    court: str | None = "Maine Supreme Judicial Court sitting as the Law Court"
    remand_reason: str | None = None
    preservation_status: str = "unknown"
    review_explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "citation": self.citation,
            "caption": self.caption,
            "docket_number": self.docket_number,
            "decision_date": self.decision_date,
            "court": self.court,
            "procedural_posture": self.procedural_posture,
            "standard_of_review": self.standard_of_review,
            "disposition": self.disposition,
            "holding": self.holding,
            "remand_reason": self.remand_reason,
            "preservation_status": self.preservation_status,
            "review_explanation": self.review_explanation,
            "issue_labels": list(self.issue_labels),
            "red_flags": list(self.red_flags),
            "appellate_red_flags": list(self.red_flags),
            "extracted_signals": self.extracted_signals,
        }


class LawCourtIntelligenceExtractor:
    """Rule-based Maine Law Court intelligence baseline.

    The extractor is intentionally deterministic: it produces structured case
    brief fields and appellate red flags that can feed draft review without
    letting a generator certify legal correctness.
    """

    def extract_case_brief(
        self,
        text: str,
        *,
        source_id: str,
        citation: str | None = None,
    ) -> dict[str, Any]:
        lowered = text.lower()
        signals = {
            "mentions_rule_52": "rule 52" in lowered or "m.r. civ. p. 52" in lowered,
            "mentions_findings": "finding" in lowered or "findings" in lowered,
            "mentions_best_interest": "best interest" in lowered or "19-a m.r.s. § 1653" in lowered,
            "mentions_transcript_record": "transcript" in lowered or "record" in lowered,
            "mentions_improper_delegation": any(
                phrase in lowered
                for phrase in (
                    "delegate",
                    "delegated",
                    "therapist shall decide",
                    "guardian ad litem shall decide",
                    "gal shall decide",
                    "left to the therapist",
                )
            ),
            "mentions_preservation": "preserv" in lowered,
            "mentions_standard_of_review": any(
                phrase in lowered
                for phrase in ("abuse of discretion", "clear error", "clearly erroneous", "de novo")
            ),
            "mentions_pfa_family_overlap": "protection from abuse" in lowered or "pfa" in lowered,
            "mentions_remand_reason": "remand" in lowered and any(
                phrase in lowered for phrase in ("because", "insufficient", "failed", "lack of")
            ),
        }
        disposition = self._extract_disposition(lowered)
        standard = self._extract_review_standard(lowered)
        red_flags = self._extract_red_flags(lowered, signals)
        brief = LawCourtCaseBrief(
            source_id=source_id,
            citation=citation or self._extract_citation(text),
            caption=self._extract_caption(text),
            docket_number=self._extract_docket(text),
            decision_date=self._extract_decision_date(text),
            procedural_posture=self._extract_posture(lowered),
            standard_of_review=standard,
            disposition=disposition,
            holding=self._extract_holding(text),
            issue_labels=tuple(self._extract_issue_labels(lowered, signals)),
            red_flags=tuple(red_flags),
            extracted_signals=signals,
            remand_reason=self._extract_remand_reason(text) if disposition in {"remanded", "mixed"} else None,
            preservation_status=self._extract_preservation_status(lowered),
            review_explanation=self._explain_review_result(disposition, standard, red_flags),
        )
        return brief.to_dict()

    def build_brief_set(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        briefs = [
            self.extract_case_brief(
                str(record.get("text", "")),
                source_id=str(record.get("source_id") or record.get("record_id") or "unknown"),
                citation=record.get("citation"),
            )
            for record in records
        ]
        issue_counts: dict[str, int] = {}
        red_flag_counts: dict[str, int] = {}
        for brief in briefs:
            for label in brief["issue_labels"]:
                issue_counts[label] = issue_counts.get(label, 0) + 1
            for flag in brief["red_flags"]:
                red_flag_counts[flag] = red_flag_counts.get(flag, 0) + 1
        return {
            "status": "pass",
            "brief_count": len(briefs),
            "briefs": briefs,
            "issue_counts": issue_counts,
            "appellate_red_flag_counts": red_flag_counts,
        }

    def _extract_caption(self, text: str) -> str | None:
        for line in text.splitlines()[:20]:
            clean = line.strip()
            if re.search(r"\b(v\.|vs\.|versus)\b", clean, re.I):
                return clean[:200]
        match = re.search(r"([A-Z][A-Za-z'. -]+\s+v\.\s+[A-Z][A-Za-z'. -]+)", text)
        return match.group(1).strip() if match else None

    def _extract_docket(self, text: str) -> str | None:
        match = re.search(r"\b(?:Docket|No\.)\s*[:#]?\s*([A-Z]{2,}-?\d{2,}-?\d+|\d{4}\s+ME\s+\d+)", text, re.I)
        return match.group(1).strip() if match else None

    def _extract_decision_date(self, text: str) -> str | None:
        match = re.search(
            r"\b(?:Decided|Argued|Submitted)\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
            text,
        )
        if match:
            return match.group(1)
        match = re.search(r"\b(\d{4}\s+ME\s+\d+)\b", text)
        return match.group(1) if match else None

    def _extract_citation(self, text: str) -> str | None:
        match = re.search(r"\b\d{4}\s+ME\s+\d+\b", text)
        return match.group(0) if match else None

    def _extract_posture(self, lowered: str) -> str:
        if "post-judgment" in lowered or "postjudgment" in lowered:
            return "post_judgment_appeal"
        if "temporary order" in lowered:
            return "temporary_order_appeal"
        if "protection from abuse" in lowered or "pfa" in lowered:
            return "pfa_family_overlap_appeal"
        if "appeal" in lowered:
            return "appeal"
        return "unknown"

    def _extract_review_standard(self, lowered: str) -> ReviewStandard:
        standards: set[ReviewStandard] = set()
        if "abuse of discretion" in lowered:
            standards.add("abuse_of_discretion")
        if "clear error" in lowered or "clearly erroneous" in lowered:
            standards.add("clear_error")
        if "de novo" in lowered:
            standards.add("de_novo")
        if len(standards) > 1:
            return "mixed"
        return next(iter(standards), "unknown")

    def _extract_disposition(self, lowered: str) -> Disposition:
        dispositions: set[Disposition] = set()
        if re.search(r"\baffirm(?:ed|s)?\b", lowered):
            dispositions.add("affirmed")
        if re.search(r"\bvacat(?:ed|e|es)\b", lowered):
            dispositions.add("vacated")
        if re.search(r"\bremand(?:ed|s)?\b", lowered):
            dispositions.add("remanded")
        if re.search(r"\brevers(?:ed|e|es)\b", lowered):
            dispositions.add("reversed")
        if re.search(r"\bdismiss(?:ed|es)?\b", lowered):
            dispositions.add("dismissed")
        if len(dispositions) > 1:
            if dispositions <= {"vacated", "remanded"}:
                return "remanded"
            return "mixed"
        return next(iter(dispositions), "unknown")

    def _extract_holding(self, text: str) -> str | None:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            lowered = sentence.lower()
            if any(
                phrase in lowered
                for phrase in ("we hold", "we conclude", "we affirm", "we vacate", "we reverse")
            ):
                return sentence.strip()
        for sentence in sentences:
            lowered = sentence.lower()
            if "because" in lowered and any(
                word in lowered for word in ("affirm", "vacate", "remand", "reverse")
            ):
                return sentence.strip()
        return sentences[0].strip() if sentences else None

    def _extract_remand_reason(self, text: str) -> str | None:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            lowered = sentence.lower()
            if "remand" in lowered and any(
                phrase in lowered for phrase in ("because", "insufficient", "failed", "lack of")
            ):
                return sentence.strip()
        return None

    def _extract_preservation_status(self, lowered: str) -> str:
        if "not preserved" in lowered or "unpreserved" in lowered:
            return "not_preserved"
        if "preserved" in lowered:
            return "preserved"
        if "plain error" in lowered:
            return "plain_error_review"
        return "unknown"

    def _extract_issue_labels(self, lowered: str, signals: dict[str, bool]) -> list[str]:
        labels: list[str] = []
        if "parental rights" in lowered or "primary residence" in lowered or "custody" in lowered:
            labels.append("parental_rights_responsibilities")
        if "child support" in lowered:
            labels.append("child_support")
        if signals["mentions_pfa_family_overlap"]:
            labels.append("pfa_family_overlap")
        if signals["mentions_rule_52"] or signals["mentions_findings"]:
            labels.append("Rule_52_findings")
        if signals["mentions_best_interest"]:
            labels.append("best_interest_factor_gap")
        if signals["mentions_transcript_record"]:
            labels.append("transcript_record_issue")
        if signals["mentions_improper_delegation"]:
            labels.append("therapist_non_delegation")
        if signals["mentions_preservation"]:
            labels.append("appeal_preservation")
        return sorted(set(labels))

    def _extract_red_flags(self, lowered: str, signals: dict[str, bool]) -> list[str]:
        red_flags: list[str] = []
        if signals["mentions_rule_52"] and any(
            phrase in lowered for phrase in ("insufficient findings", "failed to make findings", "lack of findings")
        ):
            red_flags.append("missing Rule 52 findings")
        if signals["mentions_best_interest"] and any(
            phrase in lowered for phrase in ("did not address", "failed to consider", "insufficient evidence")
        ):
            red_flags.append("unsupported best-interest findings")
        if signals["mentions_transcript_record"] and any(
            phrase in lowered for phrase in ("no transcript", "incomplete record", "missing transcript")
        ):
            red_flags.append("missing transcript or incomplete appellate record")
        if signals["mentions_improper_delegation"]:
            red_flags.append("therapist or third-party delegated contact decision")
        if signals["mentions_pfa_family_overlap"] and any(
            phrase in lowered for phrase in ("independent analysis", "without independent")
        ):
            red_flags.append("protective-order finding imported without independent analysis")
        if signals["mentions_preservation"] and ("not preserved" in lowered or "unpreserved" in lowered):
            red_flags.append("appeal preservation problem")
        return sorted(set(red_flags))

    def _explain_review_result(
        self,
        disposition: Disposition,
        standard: ReviewStandard,
        red_flags: list[str],
    ) -> str:
        parts: list[str] = []
        if disposition != "unknown":
            parts.append(f"disposition:{disposition}")
        if standard != "unknown":
            parts.append(f"standard:{standard}")
        if red_flags:
            parts.append("red_flags:" + ",".join(red_flags))
        return "; ".join(parts) if parts else "No deterministic appellate signal extracted."
