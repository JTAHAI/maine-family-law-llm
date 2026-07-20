"""Transparent source-scope and freshness assessment for chat answers.

This module does not decide whether a legal proposition is correct. It reports
what the local answer was grounded in, whether the cited legal cards have an
explicit currentness signal, and what the cards are capable of supporting.
Private matter records are intentionally kept separate from legal authority.
"""

from __future__ import annotations

from typing import Any, Iterable


_VERIFIED_FRESHNESS = {"current", "fresh", "verified_current", "verified_fresh"}
_STALE_FRESHNESS = {"stale", "superseded", "expired", "outdated"}
_UNVERIFIED_MARKERS = (
    "seed placeholder",
    "verify current",
    "verify the current",
    "version varies",
    "official-page-version-varies",
    "needs verification",
    "needs_verification",
    "freshness unknown",
    "stale unknown",
)
_PRIMARY_TYPES = {
    "statute",
    "court_rule",
    "standing_order",
    "admin_order",
    "law_court_opinion",
    "appellate_rule",
    "evidence_rule",
    "probate_rule",
    "ecourts_rule",
    "federal_statute",
    "federal_rule",
    "federal_case_law",
    "first_circuit_opinion",
    "us_supreme_court_opinion",
}
_OFFICIAL_GUIDANCE_TYPES = {
    "court_form",
    "court_process",
    "judicial_branch_guide",
    "child_support_guidance",
    "safety_resource",
    "law_court_opinion_index",
}


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item.get("metadata") or {})


def _lane(item: dict[str, Any]) -> str:
    metadata = _metadata(item)
    return str(metadata.get("source_lane") or "legal_authority")


def _freshness_status(metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("freshness_status") or "").strip().casefold()
    combined = " ".join(
        str(metadata.get(key) or "")
        for key in ("version_label", "effective_date", "notes", "completion_status")
    ).casefold()
    if explicit in _STALE_FRESHNESS or any(marker in combined for marker in ("superseded", "stale", "outdated")):
        return "stale_or_superseded"
    if explicit in _VERIFIED_FRESHNESS and not any(marker in combined for marker in _UNVERIFIED_MARKERS):
        return "verified_current"
    if any(marker in combined for marker in _UNVERIFIED_MARKERS):
        return "needs_currentness_verification"
    # An official URL, effective date, or retrieval timestamp alone is not a
    # freshness audit. Fail visibly to an unknown state instead of inferring it.
    return "needs_currentness_verification"


def _authority_status(metadata: dict[str, Any], lane: str) -> str:
    if lane == "private_record":
        return "user_provided_private_record"
    source_type = str(metadata.get("source_type") or metadata.get("source_class") or "").strip()
    official = bool(metadata.get("official"))
    jurisdiction = str(metadata.get("jurisdiction") or "").casefold()
    if official and source_type in _PRIMARY_TYPES:
        if "maine" in jurisdiction or jurisdiction == "":
            return "official_primary_authority"
        return "official_non_maine_primary_authority"
    if official and source_type in _OFFICIAL_GUIDANCE_TYPES:
        return "official_guidance_or_form"
    if official:
        return "official_source_unclassified"
    return "unofficial_or_secondary_source"


def annotate_grounding_metadata(citations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add transparent authority and freshness labels to source cards."""

    annotated: list[dict[str, Any]] = []
    for item in citations:
        copy = dict(item)
        metadata = _metadata(copy)
        lane = str(metadata.get("source_lane") or "legal_authority")
        authority_status = _authority_status(metadata, lane)
        freshness_status = (
            "not_applicable_private_record"
            if lane == "private_record"
            else _freshness_status(metadata)
        )
        metadata["authority_status"] = authority_status
        metadata["freshness_status"] = freshness_status
        metadata["current_law_verified"] = freshness_status == "verified_current"
        metadata["support_capability"] = (
            "May support a factual statement that the text appears in the selected matter record; it is not legal authority and does not prove a disputed fact."
            if lane == "private_record"
            else "May support legal information only to the extent shown in the cited passage; currentness and proposition fit still require review."
        )
        copy["metadata"] = metadata
        annotated.append(copy)
    return annotated


def assess_grounding_integrity(
    citations: Iterable[dict[str, Any]],
    *,
    search_mode: str,
) -> dict[str, Any]:
    """Summarize source lanes, authority strength, and currentness limits."""

    cards = list(citations)
    legal_cards = [item for item in cards if _lane(item) != "private_record"]
    record_cards = [item for item in cards if _lane(item) == "private_record"]
    official_legal = [item for item in legal_cards if bool(_metadata(item).get("official"))]
    primary_legal = [
        item
        for item in legal_cards
        if str(_metadata(item).get("authority_status") or "") == "official_primary_authority"
    ]
    verified_current = [
        item
        for item in legal_cards
        if str(_metadata(item).get("freshness_status") or "") == "verified_current"
    ]
    stale = [
        item
        for item in legal_cards
        if str(_metadata(item).get("freshness_status") or "") == "stale_or_superseded"
    ]
    needs_verification = [
        item
        for item in legal_cards
        if str(_metadata(item).get("freshness_status") or "") == "needs_currentness_verification"
    ]

    if legal_cards and record_cards:
        source_scope = "combined_legal_sources_and_private_records"
    elif legal_cards:
        source_scope = "legal_sources_only"
    elif record_cards:
        source_scope = "private_records_only"
    else:
        source_scope = "no_retrieved_sources"

    if not legal_cards:
        current_law_status = "not_assessed_no_legal_sources"
        current_law_verified = False
    elif stale:
        current_law_status = "blocked_stale_or_superseded_source_present"
        current_law_verified = False
    elif len(verified_current) == len(legal_cards):
        current_law_status = "verified_current_for_all_retrieved_legal_cards"
        current_law_verified = True
    elif verified_current:
        current_law_status = "mixed_currentness_requires_review"
        current_law_verified = False
    else:
        current_law_status = "not_verified_from_local_source_bundle"
        current_law_verified = False

    warnings: list[str] = []
    if legal_cards and not current_law_verified:
        warnings.append(
            "The retrieved legal cards are source-backed, but this local bundle does not establish that every card is current law. Verify the live official source before relying on a current-law statement."
        )
    if stale:
        warnings.append(
            "At least one retrieved legal card is marked stale or superseded and must not be used for a current-law conclusion."
        )
    if record_cards:
        warnings.append(
            "Private record cards show text from the selected matter only. They are not legal authority and do not establish that an allegation is true."
        )
    if not cards:
        warnings.append("No source card was retrieved for this answer.")

    source_types = sorted(
        {
            str(_metadata(item).get("source_type") or _metadata(item).get("source_class") or "unknown")
            for item in legal_cards
        }
    )
    source_ids = {
        str(item.get("source_id") or _metadata(item).get("source_id") or _metadata(item).get("id") or "")
        for item in cards
    }
    source_ids.discard("")

    return {
        "schema_version": "grounding_integrity_v1",
        "search_mode": str(search_mode or "maine_law"),
        "source_scope": source_scope,
        "source_card_count": len(cards),
        "distinct_source_count": len(source_ids),
        "legal_source_count": len(legal_cards),
        "private_record_count": len(record_cards),
        "official_legal_source_count": len(official_legal),
        "official_primary_authority_count": len(primary_legal),
        "verified_current_legal_source_count": len(verified_current),
        "needs_currentness_verification_count": len(needs_verification),
        "stale_or_superseded_count": len(stale),
        "legal_source_types": source_types,
        "current_law_status": current_law_status,
        "current_law_verified": current_law_verified,
        "review_required": True,
        "warnings": list(dict.fromkeys(warnings)),
        "support_boundaries": [
            "A retrieved legal source may support a legal proposition only after the cited passage and currentness are checked.",
            "A private record may show that text appears in the selected file; it does not prove the underlying allegation.",
            "Source presence is not the same as claim support, negative-treatment review, or filing readiness.",
        ],
    }
