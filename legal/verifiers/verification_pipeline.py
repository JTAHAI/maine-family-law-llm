from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from legal.verifiers.authority_status_verifier import AuthorityStatusVerifier
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.claim_support_verifier import ClaimSupportVerifier, extract_legal_claims
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier
from legal.verifiers.source_cards import SourceCardStore
from legal.verifiers.staleness_jurisdiction import FreshnessJurisdictionTreatmentChecker

BLOCKING_CITATION_STATUSES = {"not_found"}
BLOCKING_QUOTE_STATUSES = {"quote_span_not_found", "semantic_match"}
BLOCKING_CLAIM_STATUSES = {
    "partially_supported",
    "unsupported",
    "contradicted",
    "stale",
    "jurisdiction_mismatch",
    "not_verifiable",
}


@dataclass(frozen=True)
class QuoteRequest:
    quoted_text: str
    source_id: str


@dataclass(frozen=True)
class ClaimRequest:
    claim: str
    source_ids: tuple[str, ...] = ()


@dataclass
class LegalVerificationReport:
    citations: list[dict[str, Any]] = field(default_factory=list)
    quotes: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    authorities: list[dict[str, Any]] = field(default_factory=list)
    source_scope: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    @property
    def filing_ready_possible(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": self.citations,
            "quotes": self.quotes,
            "claims": self.claims,
            "authorities": self.authorities,
            "source_scope": self.source_scope,
            "blockers": self.blockers,
            "filing_ready_possible": self.filing_ready_possible,
        }


class LegalOutputVerifier:
    """Verify legal output without trusting the generator.

    Inputs are deliberately explicit: the caller supplies the generated text,
    admitted source text by source_id, optional source cards/metadata, and optional
    claim/quote requests. The verifier returns blockers for filing-ready gates.
    """

    def __init__(self, authority_index: SourceAuthorityIndex | None = None) -> None:
        self.authority_index = authority_index or SourceAuthorityIndex()
        self.quote_verifier = QuoteSpanVerifier()
        self.claim_verifier = ClaimSupportVerifier()
        self.authority_verifier = AuthorityStatusVerifier()
        self.scope_checker = FreshnessJurisdictionTreatmentChecker()

    def verify_output(
        self,
        *,
        text: str,
        source_texts: dict[str, str] | None = None,
        source_metadata: dict[str, dict[str, Any]] | None = None,
        source_cards: dict[str, dict[str, Any]] | SourceCardStore | None = None,
        quotes: Iterable[QuoteRequest | dict[str, str]] | None = None,
        claims: Iterable[ClaimRequest | dict[str, Any] | str] | None = None,
        auto_extract_claims: bool = False,
        auto_extract_quotes: bool = True,
        expected_jurisdiction: str = "maine",
    ) -> dict[str, Any]:
        source_texts = source_texts or {}
        source_metadata = source_metadata or {}
        card_store = _coerce_source_cards(source_cards, source_metadata)
        report = LegalVerificationReport()

        for resolution in self.authority_index.resolve_text(text):
            item = resolution.to_dict()
            source_id = item.get("source_id")
            item["source_card"] = card_store.get(source_id) if source_id else None
            item["pinpoint_support"] = _pinpoint_citation_support(
                text=source_texts.get(str(source_id), "") if source_id else "",
                normalized_citation=resolution.citation.normalized,
                raw_citation=resolution.citation.raw,
                metadata=source_metadata.get(str(source_id), {}) if source_id else {},
            )
            report.citations.append(item)
            if resolution.status in BLOCKING_CITATION_STATUSES:
                report.blockers.append(f"citation_not_found:{resolution.citation.normalized}")

        for source_id, metadata in source_metadata.items():
            authority = self.authority_verifier.verify_source(
                metadata,
                expected_jurisdiction=expected_jurisdiction,
            ).to_dict()
            authority["source_card"] = card_store.get(source_id)
            report.authorities.append(authority)
            if not authority["verified"]:
                report.blockers.append(f"authority_not_verified:{source_id}")

        scope_report = self.scope_checker.check(
            text=text,
            source_metadata=source_metadata,
            expected_jurisdiction=expected_jurisdiction,
        )
        report.source_scope = scope_report
        report.blockers.extend(scope_report.get("blockers", []))

        quote_inputs = list(quotes) if quotes is not None else (_extract_inline_quotes(text) if auto_extract_quotes else [])
        for quote_request in quote_inputs:
            request = _coerce_quote_request(quote_request)
            source_text = source_texts.get(request.source_id, "")
            verification = self.quote_verifier.verify(source_text, request.quoted_text)
            verification["source_id"] = request.source_id
            verification["source_card"] = card_store.get(request.source_id)
            report.quotes.append(verification)
            if verification["status"] in BLOCKING_QUOTE_STATUSES:
                report.blockers.append(f"quote_span_not_found:{request.source_id}")

        claim_inputs = list(claims or [])
        if auto_extract_claims:
            # Explicit requests may add coverage, never hide unlisted assertions.
            seen_claims = {_coerce_claim_request(row).claim for row in claim_inputs}
            claim_inputs.extend(ClaimRequest(claim=claim) for claim in extract_legal_claims(text)
                                if claim not in seen_claims)
        for claim_request in claim_inputs:
            request = _coerce_claim_request(claim_request)
            selected_ids = request.source_ids or tuple(source_texts)
            evidence = [source_texts[source_id] for source_id in selected_ids if source_id in source_texts]
            statuses = [
                source_metadata.get(source_id, {}).get("authority_status", "stale_unknown")
                for source_id in selected_ids
                if source_id in source_metadata
            ]
            jurisdictions = [
                source_metadata.get(source_id, {}).get("jurisdiction", expected_jurisdiction)
                for source_id in selected_ids
                if source_id in source_metadata
            ]
            source_classes = [
                source_metadata.get(source_id, {}).get("source_class", "unknown")
                for source_id in selected_ids
                if source_id in source_metadata
            ]
            verification = self.claim_verifier.verify(
                request.claim,
                evidence,
                authority_statuses=statuses,
                source_jurisdictions=jurisdictions,
                source_ids=selected_ids,
                source_classes=source_classes,
                expected_jurisdiction=expected_jurisdiction,
            )
            verification["source_ids"] = list(selected_ids)
            verification["source_cards"] = [card_store.get(source_id) for source_id in selected_ids]
            report.claims.append(verification)
            if verification["status"] != "supported" or verification.get("supported") is not True:
                report.blockers.append(f"claim_{verification['status']}")

        report.blockers = sorted(set(report.blockers))
        return report.to_dict()


def _extract_inline_quotes(text: str) -> list[QuoteRequest]:
    # Inline quotes without a source_id cannot be verified. Assign a marker to
    # force the missing-source blocker rather than treating them as verified.
    return [
        QuoteRequest(quoted_text=match.group(1), source_id="__missing_source__")
        for match in re.finditer(r'"([^"]{8,})"', text)
    ]


def _coerce_quote_request(value: QuoteRequest | dict[str, str]) -> QuoteRequest:
    if isinstance(value, QuoteRequest):
        return value
    return QuoteRequest(quoted_text=value["quoted_text"], source_id=value["source_id"])


def _coerce_claim_request(value: ClaimRequest | dict[str, Any] | str) -> ClaimRequest:
    if isinstance(value, ClaimRequest):
        return value
    if isinstance(value, str):
        return ClaimRequest(claim=value)
    return ClaimRequest(claim=value["claim"], source_ids=tuple(value.get("source_ids", ())))


def _coerce_source_cards(
    source_cards: dict[str, dict[str, Any]] | SourceCardStore | None,
    source_metadata: dict[str, dict[str, Any]],
) -> SourceCardStore:
    if isinstance(source_cards, SourceCardStore):
        return source_cards
    if source_cards:
        return SourceCardStore(source_cards.values())
    return SourceCardStore(source_metadata.values())


def _pinpoint_citation_support(
    *,
    text: str,
    normalized_citation: str,
    raw_citation: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if not text and not metadata:
        return {"status": "source_text_not_available", "supported": False}
    citation_metadata = str(metadata.get("citation") or metadata.get("normalized_citation") or "")
    if citation_metadata and normalized_citation.lower() == citation_metadata.lower():
        return {"status": "metadata_citation_match", "supported": True}
    for needle in (raw_citation, normalized_citation):
        if needle and text:
            start = text.lower().find(needle.lower())
            if start >= 0:
                return {
                    "status": "source_text_citation_match",
                    "supported": True,
                    "start_offset": start,
                    "end_offset": start + len(needle),
                }
    return {"status": "citation_not_pinpointed_in_source_text", "supported": False}
