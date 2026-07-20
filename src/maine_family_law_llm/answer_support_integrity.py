"""Conservative claim-to-source diagnostics for local chat answers.

This layer does not certify legal entailment. It extracts candidate legal claims,
checks for lexical candidate support in retrieved legal passages, and reports
where a human reviewer must inspect the proposition, citation, currentness, and
negative treatment before relying on the answer.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from legal.verifiers.claim_support_verifier import ClaimSupportVerifier, extract_legal_claims

_CURRENT_LAW_PATTERNS = (
    re.compile(r"\bunder\s+(?:current\s+)?maine\s+law\b", re.I),
    re.compile(r"\bmaine\s+law\s+(?:requires?|prohibits?|allows?|provides?)\b", re.I),
    re.compile(r"\b(?:must|shall|required|deadline|within\s+\d+\s+days?)\b", re.I),
)


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item.get("metadata") or {})


def assess_answer_support_integrity(
    answer_text: str,
    citations: Iterable[dict[str, Any]],
    *,
    grounding_integrity: dict[str, Any] | None = None,
    max_claims: int = 12,
) -> dict[str, Any]:
    cards = list(citations)
    legal_cards = [
        item for item in cards
        if str(_metadata(item).get("source_lane") or "legal_authority") != "private_record"
    ]
    claims = extract_legal_claims(str(answer_text or ""))[:max_claims]
    evidence = [str(item.get("snippet") or _metadata(item).get("text_excerpt") or "") for item in legal_cards]
    source_ids = [str(item.get("source_id") or _metadata(item).get("id") or "") for item in legal_cards]
    jurisdictions = [str(_metadata(item).get("jurisdiction") or "Maine") for item in legal_cards]
    authority_statuses = [str(_metadata(item).get("freshness_status") or "") for item in legal_cards]

    verifier = ClaimSupportVerifier()
    results = [
        verifier.verify(
            claim,
            evidence,
            authority_statuses=authority_statuses,
            expected_jurisdiction="maine",
            source_jurisdictions=jurisdictions,
            source_ids=source_ids,
        )
        for claim in claims
    ]
    counts = {
        status: sum(1 for result in results if result.get("status") == status)
        for status in (
            "supported", "partially_supported", "unsupported", "contradicted",
            "stale", "jurisdiction_mismatch", "not_verifiable",
        )
    }
    current_law_language = any(pattern.search(str(answer_text or "")) for pattern in _CURRENT_LAW_PATTERNS)
    grounding = dict(grounding_integrity or {})
    blockers: list[str] = []
    warnings: list[str] = []
    if claims and not legal_cards:
        blockers.append("legal_claims_without_legal_source_cards")
    if counts["unsupported"]:
        blockers.append("candidate_legal_claims_without_lexical_source_support")
    if counts["contradicted"]:
        blockers.append("candidate_claim_polarity_conflict")
    if counts["stale"] or int(grounding.get("stale_or_superseded_count") or 0):
        blockers.append("stale_or_superseded_source_in_claim_support_set")
    if counts["jurisdiction_mismatch"]:
        blockers.append("jurisdiction_mismatch_in_claim_support_set")
    if current_law_language and not bool(grounding.get("current_law_verified")):
        blockers.append("current_law_language_requires_live_official_verification")
    if counts["partially_supported"]:
        warnings.append("One or more legal claims have only partial lexical overlap with a retrieved passage.")
    if results:
        warnings.append(
            "Lexical claim matching is a review aid only; it does not establish legal entailment, currentness, negative treatment, or filing readiness."
        )

    if not claims:
        status = "no_candidate_legal_claims_detected"
    elif blockers:
        status = "review_blocked"
    elif all(result.get("status") == "supported" for result in results):
        status = "candidate_support_found_review_required"
    else:
        status = "review_required"

    return {
        "schema_version": "answer_support_integrity_v1",
        "status": status,
        "candidate_legal_claim_count": len(claims),
        "legal_source_card_count": len(legal_cards),
        "current_law_language_detected": current_law_language,
        "status_counts": counts,
        "claim_results": results,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "human_review_required": True,
        "filing_ready": False,
    }
