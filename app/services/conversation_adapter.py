from __future__ import annotations

from typing import Any

from app.services.status_labels import blocked_state_explanations, stable_status_labels
from legal.conversation import ConversationService


class ConversationAdapter:
    def __init__(self) -> None:
        self.service = ConversationService()

    def for_query(self, payload: dict[str, Any], *, audience_hint: str | None = None) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="query",
            payload=payload,
            audience_hint=audience_hint,
        )
        response.update(
            {
                "status": "review_required",
                "query": payload.get("query"),
                "answer": response["short_answer"],
                "claims": [],
                "drilldown": {
                    "answer_to_claim_to_citation_to_source_text_to_verifier_result": True,
                    "claim": None,
                    "citation": response["citations"][0]["citation"] if response["citations"] else None,
                    "source_text": None,
                    "verifier_result": response["claim_support_status"],
                },
                "message": response["warnings"][0] if response["warnings"] else response["short_answer"],
                "source_card_count": len(response["source_cards"]),
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_research(self, payload: dict[str, Any], *, audience_hint: str | None = None) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="research",
            payload=payload,
            audience_hint=audience_hint,
            requested_renderer="authority_matrix",
        )
        response.update(
            {
                "status": "review_required",
                "query": payload.get("query"),
                "retrieved_sources": payload.get("retrieved_sources", []),
                "source_card_count": len(response["source_cards"]),
                "message": response["short_answer"],
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_draft(
        self,
        payload: dict[str, Any],
        workspace: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="draft",
            payload=payload,
            result=workspace,
            audience_hint=audience_hint,
            requested_renderer="draft_review",
        )
        response.update(workspace)
        response.update(
            {
                "status": "review_required",
                "review_status": workspace.get("review_status", "review_required"),
                "blocked_export_explanation": workspace.get("blocked_export_explanation", []),
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_review(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="review",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="document_review",
        )
        response.update(result)
        response.update(
            {
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_citation_verification(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="citation_verification",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="citation_report",
        )
        response.update(result)
        response.update(
            {
                "status": "review_required",
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_quote_verification(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="quote_verification",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="quote_report",
        )
        response.update(result)
        response.update(
            {
                "status": "review_required",
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_evidence_map(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="evidence_map",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="evidence_map",
        )
        response.update(result)
        response.update(
            {
                "status": "review_required",
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_timeline(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="timeline",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="timeline",
        )
        response.update(result)
        response.update(
            {
                "status": "review_required",
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response

    def for_filing_ready(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        audience_hint: str | None = None,
    ) -> dict[str, Any]:
        response = self.service.build_response(
            task_type="filing_ready_check",
            payload=payload,
            result=result,
            audience_hint=audience_hint,
            requested_renderer="why_not_filing_ready_report",
        )
        response.update(result)
        response.update(
            {
                "status": "review_required" if result.get("blockers") else "filing_ready_passed",
                "blocked_export_explanation": result.get("blockers", []),
                "status_labels": stable_status_labels(),
                "blocked_state_explanations": blocked_state_explanations(),
            }
        )
        return response
