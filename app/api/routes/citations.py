from __future__ import annotations

from fastapi import APIRouter, Header

from app.api.security import review_response, strict_json_bool
from app.services import ConversationAdapter
from legal.verifiers.citation_parser import extract_citations
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.verification_pipeline import LegalOutputVerifier

router = APIRouter(tags=["verification"])
adapter = ConversationAdapter()


def _demo_index() -> SourceAuthorityIndex:
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-19a-1653")
    index.add_rule("M.R. Civ. P. 120", "source-rule-120")
    index.add_form("FM-002", "source-form-fm-002")
    return index


@router.post("/citations/verify", summary="Resolve and verify citations")
def verify_citations(
    payload: dict,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    text = payload.get("text", "")
    index = SourceAuthorityIndex.from_rows(payload.get("citation_index", [])) if payload.get("citation_index") else _demo_index()
    verifier = LegalOutputVerifier(index)
    report = verifier.verify_output(
        text=text,
        source_texts=payload.get("source_texts") or {},
        source_metadata=payload.get("source_metadata") or {},
        source_cards=payload.get("source_cards") or None,
        quotes=payload.get("quotes"),
        claims=payload.get("claims"),
        auto_extract_claims=strict_json_bool(payload, "auto_extract_claims", default=False),
    )
    response = adapter.for_citation_verification(
        payload,
        {
            "citations": [citation.to_dict() for citation in extract_citations(text)],
            "resolutions": report["citations"],
            "verification_report": report,
        },
        audience_hint=x_user_role,
    )
    return review_response("POST /api/citations/verify", "citation_verification", response)
