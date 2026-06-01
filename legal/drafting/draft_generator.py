from __future__ import annotations

from typing import Any

from legal.drafting.templates import get_template


class DraftGenerator:
    def generate_motion_template(self, issue_type: str) -> dict[str, Any]:
        return self.generate_review_required_draft(
            template_id="motion",
            issue_type=issue_type,
            facts=[],
            authorities=[],
        )

    def generate_review_required_draft(
        self,
        *,
        template_id: str,
        issue_type: str,
        facts: list[dict[str, Any]] | list[str],
        authorities: list[dict[str, Any]],
        requested_relief: str = "",
    ) -> dict[str, Any]:
        template = get_template(template_id)
        normalized_facts = [fact if isinstance(fact, str) else fact.get("fact", fact.get("text", "")) for fact in facts]
        source_cards = [authority for authority in authorities if authority.get("source_id") or authority.get("citation")]
        authority_matrix = [
            {
                "source_id": authority.get("source_id"),
                "citation": authority.get("citation"),
                "authority_status": authority.get("authority_status", authority.get("status", "unverified")),
                "relevance": authority.get("relevance", authority.get("score", 0)),
            }
            for authority in authorities
        ]
        sections = {section: "" for section in template.required_sections}
        if "facts" in sections:
            sections["facts"] = "\n".join(f"- {fact}" for fact in normalized_facts)
        if "numbered_facts" in sections:
            sections["numbered_facts"] = "\n".join(f"{idx + 1}. {fact}" for idx, fact in enumerate(normalized_facts))
        if "requested_relief" in sections:
            sections["requested_relief"] = requested_relief
        if "authority" in sections:
            sections["authority"] = "\n".join(
                f"- {item.get('citation') or item.get('source_id')}: {item.get('authority_status')}"
                for item in authority_matrix
            )
        if "sources" in sections:
            sections["sources"] = "\n".join(
                f"- {item.get('citation') or item.get('source_id')}" for item in authority_matrix
            )

        return {
            "template_id": template.template_id,
            "title": f"{template.title}: {issue_type}",
            "issue_type": issue_type,
            "sections": sections,
            "source_cards": source_cards,
            "authority_matrix": authority_matrix,
            "fact_to_evidence_map": [],
            "citation_report": [],
            "quote_report": [],
            "human_review_checklist": template.review_gates,
            "review_required": True,
            "filing_ready": False,
            "export_status": "blocked_review_required",
        }
