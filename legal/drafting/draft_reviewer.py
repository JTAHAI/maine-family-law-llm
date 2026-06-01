from __future__ import annotations

from typing import Any

from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from legal.drafting.templates import get_template


class DraftReviewer:
    REQUIRED_SECTIONS = [
        "caption",
        "facts",
        "requested_relief",
    ]

    def review(self, draft: dict[str, Any]) -> dict[str, Any]:
        template = get_template(draft.get("template_id", "motion"))
        sections = draft.get("sections", draft)
        required = template.required_sections if draft.get("template_id") else self.REQUIRED_SECTIONS
        missing_sections = [section for section in required if not sections.get(section)]

        blockers = []
        if missing_sections:
            blockers.extend(f"missing_section:{section}" for section in missing_sections)
        if not draft.get("source_cards"):
            blockers.append("source_cards_missing")
        if not draft.get("authority_matrix"):
            blockers.append("authority_matrix_missing")
        if "fact_to_evidence_map" in draft and not draft.get("fact_to_evidence_map"):
            blockers.append("fact_to_evidence_map_missing")
        if not draft.get("citation_report"):
            blockers.append("citation_report_missing")
        if not draft.get("quote_report"):
            blockers.append("quote_report_missing")
        if not draft.get("human_review_complete", False):
            blockers.append("human_review_complete")

        findings_report = None
        text = draft.get("text") or "\n".join(str(v) for v in sections.values() if isinstance(v, str))
        if draft.get("requires_findings_review") or any(
            term in text.lower() for term in ("parental rights", "primary residence", "protection from abuse", "supervised contact")
        ):
            findings_report = Rule52BestInterestFindingsEngine().review_order(
                text,
                posture=str(draft.get("posture", "final_order")),
            ).to_dict()
            blockers.extend(f"findings:{blocker}" for blocker in findings_report["blockers"])

        appellate_red_flags: list[str] = []
        for brief in draft.get("law_court_briefs", []) or []:
            for flag in brief.get("appellate_red_flags", brief.get("red_flags", [])):
                appellate_red_flags.append(flag)
                blockers.append(f"appellate_red_flag:{flag}")

        blockers = sorted(set(blockers))
        return {
            "review_required": True,
            "missing_sections": missing_sections,
            "blockers": blockers,
            "ready_for_human_review": len([b for b in blockers if b.startswith("missing_section:")]) == 0,
            "filing_ready": False,
            "export_status": "blocked" if blockers else "review_required",
            "human_review_checklist": draft.get("human_review_checklist", []),
            "findings_review": findings_report,
            "appellate_red_flags": sorted(set(appellate_red_flags)),
        }
