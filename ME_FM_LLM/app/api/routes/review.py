from __future__ import annotations

from fastapi import APIRouter

from app.api.security import review_response
from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.verification_pipeline import LegalOutputVerifier

router = APIRouter(tags=["review"])


@router.post("/review", summary="Review a draft or uploaded text")
def review(payload: dict):
    index = SourceAuthorityIndex.from_rows(payload.get("citation_index", [])) if payload.get("citation_index") else SourceAuthorityIndex()
    verifier = LegalOutputVerifier(index)
    report = verifier.verify_output(
        text=payload.get("text", ""),
        source_texts=payload.get("source_texts") or {},
        source_metadata=payload.get("source_metadata") or {},
        source_cards=payload.get("source_cards") or None,
        quotes=payload.get("quotes"),
        claims=payload.get("claims"),
        auto_extract_claims=bool(payload.get("auto_extract_claims", True)),
    )
    return review_response(
        "POST /api/review",
        "draft_or_text_review",
        {
            "status": "review_required" if report["blockers"] else "verified_pending_human_review",
            "verification_report": report,
            "missing_sections": payload.get("missing_sections", []),
        },
    )


@router.post("/filing-ready/check", summary="Evaluate filing-readiness blockers")
def filing_ready(payload: dict):
    result = FilingReadyGate().evaluate(payload)
    result["blocked_export_explanation"] = result.get("blockers", [])
    return review_response("POST /api/filing-ready/check", "filing_ready_gate", result)
