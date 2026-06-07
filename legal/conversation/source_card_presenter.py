from __future__ import annotations

from typing import Any

from legal.verifiers.source_cards import SourceCard, SourceCardStore


STATUS_LABELS = {
    "source_verified": "Source verified",
    "source_unknown_freshness": "Source freshness unknown",
    "source_stale": "Source may be stale",
    "citation_not_found": "Citation not found",
    "citation_unverified": "Citation unverified",
    "quote_span_not_found": "Quote span not found",
    "unsupported_claim": "Unsupported claim",
    "partially_supported_claim": "Partially supported claim",
    "contradicted_claim": "Contradicted claim",
    "jurisdiction_mismatch": "Jurisdiction mismatch",
    "review_required": "Review required",
    "blocked_from_filing_ready": "Blocked from filing-ready",
    "filing_ready_passed": "Filing-ready gate passed",
}


class SourceCardPresenter:
    def present(self, cards: list[dict[str, Any]] | SourceCardStore | None) -> list[dict[str, Any]]:
        if isinstance(cards, SourceCardStore):
            rows = list(cards.to_dict().values())
        else:
            rows = list(cards or [])
        presented: list[dict[str, Any]] = []
        for row in rows:
            source_card = SourceCard.from_mapping(row).to_dict()
            source_status = self._source_status(source_card)
            source_card["status_label"] = STATUS_LABELS[source_status]
            source_card["source_scope_status"] = source_status
            source_card["can_support_current_law_claim"] = source_status == "source_verified"
            source_card["review_required"] = True
            presented.append(source_card)
        return presented

    def _source_status(self, card: dict[str, Any]) -> str:
        freshness = str(card.get("freshness_status") or "unknown").lower()
        authority = str(card.get("authority_status") or "").lower()
        jurisdiction = str(card.get("jurisdiction") or "maine").lower()
        if jurisdiction not in {"maine", "federal"}:
            return "jurisdiction_mismatch"
        if freshness in {"fresh", "fresh_verified"} and authority.startswith("verified"):
            return "source_verified"
        if freshness in {"stale", "stale_unknown", "must_verify_current_official_source"}:
            return "source_stale"
        return "source_unknown_freshness"
