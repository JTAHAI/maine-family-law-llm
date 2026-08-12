from __future__ import annotations

from fastapi import APIRouter, Header

from app.api.security import review_response, strict_json_bool
from app.services import ConversationAdapter
from legal.drafting.workspace import DraftWorkspaceBuilder

router = APIRouter(tags=["drafting"])
adapter = ConversationAdapter()


@router.post("/draft", summary="Generate a review-required draft workspace")
def draft(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    workspace = DraftWorkspaceBuilder().build(
        template_id=payload.get("template_id", "motion"),
        issue_type=payload.get("issue_type", "maine_family_law_issue"),
        facts=payload.get("facts", []),
        authorities=payload.get("authorities", []),
        requested_relief=payload.get("requested_relief", ""),
        fact_to_evidence_map=payload.get("fact_to_evidence_map"),
        citation_report=payload.get("citation_report"),
        quote_report=payload.get("quote_report"),
        claim_support_report=payload.get("claim_support_report"),
        missing_facts=payload.get("missing_facts"),
        procedure_posture_report=payload.get("procedure_posture_report"),
        forms_report=payload.get("forms_report"),
        human_review_complete=strict_json_bool(payload, "human_review_complete", default=False),
        provenance_receipt=payload.get("provenance_receipt"),
    ).to_dict()
    workspace["review_status"] = "review_required"
    workspace["blocked_export_explanation"] = workspace.get("filing_ready_gate", {}).get("blockers", [])
    response = adapter.for_draft(payload, workspace, audience_hint=x_user_role)
    return review_response("POST /api/draft", "draft_workspace", response)
