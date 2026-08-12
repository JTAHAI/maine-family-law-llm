from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal.drafting.draft_generator import DraftGenerator
from legal.drafting.draft_reviewer import DraftReviewer
from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.drafting.provenance import validate_provenance_receipt


@dataclass(frozen=True)
class DraftWorkspace:
    draft: dict[str, Any]
    sidebars: dict[str, Any]
    review: dict[str, Any]
    filing_ready_gate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft": self.draft,
            "sidebars": self.sidebars,
            "review": self.review,
            "filing_ready_gate": self.filing_ready_gate,
            "review_required": True,
            "export_status": self.filing_ready_gate["export_status"],
        }


class DraftWorkspaceBuilder:
    """Builds the Pass 37 review-required drafting workspace.

    The workspace keeps drafting useful while preserving legal safety: all drafts
    default to review_required and carry sidebars/reports that feed the Pass 38
    filing-ready gate.
    """

    def build(
        self,
        *,
        template_id: str,
        issue_type: str,
        facts: list[dict[str, Any]] | list[str],
        authorities: list[dict[str, Any]],
        requested_relief: str = "",
        fact_to_evidence_map: list[dict[str, Any]] | None = None,
        citation_report: list[dict[str, Any]] | None = None,
        quote_report: list[dict[str, Any]] | None = None,
        claim_support_report: dict[str, Any] | None = None,
        missing_facts: list[str] | None = None,
        procedure_posture_report: dict[str, Any] | None = None,
        forms_report: dict[str, Any] | None = None,
        human_review_complete: bool = False,
        provenance_receipt: dict[str, Any] | None = None,
    ) -> DraftWorkspace:
        draft = DraftGenerator().generate_review_required_draft(
            template_id=template_id,
            issue_type=issue_type,
            facts=facts,
            authorities=authorities,
            requested_relief=requested_relief,
        )
        draft["fact_to_evidence_map"] = fact_to_evidence_map or []
        draft["citation_report"] = citation_report or []
        draft["quote_report"] = quote_report or []
        draft["claim_support_report"] = claim_support_report or {"claims": []}
        draft["missing_fact_sidebar"] = self._missing_fact_sidebar(facts, fact_to_evidence_map or [], missing_facts or [])
        draft["claim_support_sidebar"] = self._claim_support_sidebar(draft["claim_support_report"])
        draft["source_card_sidebar"] = self._source_card_sidebar(draft.get("source_cards", []))
        draft["procedure_posture_report"] = procedure_posture_report or {}
        draft["forms_report"] = forms_report or {}
        draft["generation_provenance"] = validate_provenance_receipt(provenance_receipt)
        draft["human_review_complete"] = human_review_complete
        draft["review_required"] = True
        draft["filing_ready"] = False
        draft["export_status"] = "blocked_review_required"

        review = DraftReviewer().review(draft)
        gate_payload = {
            **draft,
            "authority_matrix": draft.get("authority_matrix", []),
            "review_required": True,
            "human_review_complete": human_review_complete,
        }
        gate = FilingReadyGate().evaluate(gate_payload)
        sidebars = {
            "source_cards": draft["source_card_sidebar"],
            "authority_matrix": draft.get("authority_matrix", []),
            "claim_support": draft["claim_support_sidebar"],
            "missing_facts": draft["missing_fact_sidebar"],
            "citation_report": draft["citation_report"],
            "quote_report": draft["quote_report"],
            "generation_provenance": draft["generation_provenance"],
        }
        return DraftWorkspace(draft=draft, sidebars=sidebars, review=review, filing_ready_gate=gate)

    def _source_card_sidebar(self, source_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sidebar = []
        for card in source_cards:
            sidebar.append(
                {
                    "source_id": card.get("source_id"),
                    "citation": card.get("citation"),
                    "title": card.get("title"),
                    "jurisdiction": card.get("jurisdiction", "maine"),
                    "authority_status": card.get("authority_status", card.get("status", "unverified")),
                    "freshness_status": card.get("freshness_status", "unknown"),
                    "drilldown_available": bool(card.get("source_id")),
                }
            )
        return sidebar

    def _claim_support_sidebar(self, claim_support_report: dict[str, Any]) -> dict[str, Any]:
        claims = claim_support_report.get("claims", []) if isinstance(claim_support_report, dict) else []
        unsupported = [
            claim for claim in claims
            if str(claim.get("support_status", claim.get("status", ""))).lower()
            not in {"supported", "partially_supported"}
        ]
        return {
            "claims": claims,
            "unsupported_claims": unsupported,
            "unsupported_count": len(unsupported),
            "review_required": True,
        }

    def _missing_fact_sidebar(
        self,
        facts: list[dict[str, Any]] | list[str],
        fact_to_evidence_map: list[dict[str, Any]],
        explicit_missing: list[str],
    ) -> dict[str, Any]:
        mapped_text = {
            str(row.get("fact") or row.get("fact_text") or row.get("fact_id") or "").strip().lower()
            for row in fact_to_evidence_map
            if row.get("source_document_id") or row.get("source_document_ids")
        }
        missing = list(explicit_missing)
        for item in facts:
            fact = item if isinstance(item, str) else item.get("fact", item.get("text", ""))
            if fact and fact.strip().lower() not in mapped_text:
                missing.append(fact)
        # Stable unique order.
        unique_missing = list(dict.fromkeys(missing))
        return {
            "missing_facts": unique_missing,
            "missing_count": len(unique_missing),
            "review_required": bool(unique_missing),
        }
