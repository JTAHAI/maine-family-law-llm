from __future__ import annotations

from fastapi import APIRouter, Header

from app.api.security import review_response, strict_json_bool
from app.services import ConversationAdapter
from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.verification_pipeline import LegalOutputVerifier

router = APIRouter(tags=["review"])
adapter = ConversationAdapter()


@router.post("/review", summary="Review a draft or uploaded text")
def review(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    index = SourceAuthorityIndex.from_rows(payload.get("citation_index", [])) if payload.get("citation_index") else SourceAuthorityIndex()
    verifier = LegalOutputVerifier(index)
    report = verifier.verify_output(
        text=payload.get("text", ""),
        source_texts=payload.get("source_texts") or {},
        source_metadata=payload.get("source_metadata") or {},
        source_cards=payload.get("source_cards") or None,
        quotes=payload.get("quotes"),
        claims=payload.get("claims"),
        auto_extract_claims=strict_json_bool(payload, "auto_extract_claims", default=True),
    )
    response = adapter.for_review(
        payload,
        {
            "status": "review_required" if report["blockers"] else "verified_pending_human_review",
            "verification_report": report,
            "missing_sections": payload.get("missing_sections", []),
        },
        audience_hint=x_user_role,
    )
    return review_response("POST /api/review", "draft_or_text_review", response)


@router.post("/filing-ready/check", summary="Evaluate filing-readiness blockers")
def filing_ready(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    result = FilingReadyGate().evaluate(payload)
    result["blocked_export_explanation"] = result.get("blockers", [])
    response = adapter.for_filing_ready(payload, result, audience_hint=x_user_role)
    return review_response("POST /api/filing-ready/check", "filing_ready_gate", response)
