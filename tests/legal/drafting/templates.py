from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DraftTemplate:
    template_id: str
    title: str
    required_sections: list[str]
    review_gates: list[str] = field(default_factory=lambda: [
        "source_cards_present",
        "authority_matrix_present",
        "fact_to_evidence_map_present",
        "citation_report_present",
        "quote_report_present",
        "human_review_complete",
    ])


TEMPLATES: dict[str, DraftTemplate] = {
    "motion": DraftTemplate(
        template_id="motion",
        title="Review-required motion template",
        required_sections=["caption", "introduction", "facts", "authority", "requested_relief", "signature_block"],
    ),
    "affidavit": DraftTemplate(
        template_id="affidavit",
        title="Review-required affidavit template",
        required_sections=["caption", "affiant", "numbered_facts", "verification", "notary_block"],
    ),
    "proposed_findings": DraftTemplate(
        template_id="proposed_findings",
        title="Review-required proposed findings template",
        required_sections=["caption", "findings_of_fact", "conclusions_of_law", "order_language"],
    ),
    "objection": DraftTemplate(
        template_id="objection",
        title="Review-required objection template",
        required_sections=["caption", "objected_to", "grounds", "authority", "requested_relief"],
    ),
    "client_letter": DraftTemplate(
        template_id="client_letter",
        title="Review-required client letter template",
        required_sections=["recipient", "summary", "next_steps", "review_note"],
    ),
    "plain_language_explainer": DraftTemplate(
        template_id="plain_language_explainer",
        title="Plain-language explainer template",
        required_sections=["topic", "plain_language_summary", "sources", "limits"],
    ),
}


def get_template(template_id: str) -> DraftTemplate:
    return TEMPLATES.get(template_id, TEMPLATES["motion"])
