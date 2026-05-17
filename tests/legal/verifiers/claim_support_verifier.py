from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal

ClaimSupportStatus = Literal[
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "stale",
    "jurisdiction_mismatch",
    "not_verifiable",
]

NEGATION_TERMS = {"not", "no", "never", "cannot", "without", "insufficient", "lacks", "lack"}
STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "must",
    "shall",
    "may",
    "are",
    "was",
    "were",
    "has",
    "have",
    "into",
    "under",
    "according",
    "maine",
    "court",
}

LEGAL_CLAIM_TRIGGERS = {
    "must",
    "shall",
    "may",
    "requires",
    "required",
    "prohibits",
    "standard",
    "findings",
    "best interest",
    "parental rights",
    "support",
    "custody",
    "jurisdiction",
}


def extract_legal_claims(text: str) -> list[str]:
    """Extract legal-assertion candidate sentences from generated text or drafts.

    This is a conservative deterministic baseline for Pass 30. It intentionally
    over-includes sentences with legal modal terms or Maine/federal citations so
    downstream support verification and human review can decide what is safe.
    """
    claims: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        cleaned = sentence.strip()
        if len(cleaned) < 12:
            continue
        lowered = cleaned.lower()
        if (
            any(trigger in lowered for trigger in LEGAL_CLAIM_TRIGGERS)
            or re.search(r"\b\d+(?:-[A-Z])?\s*M\.R\.S\.", cleaned, re.I)
            or re.search(r"\b\d{4}\s+ME\s+\d+\b", cleaned)
        ):
            claims.append(cleaned)
    return claims


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _has_negation(text: str) -> bool:
    return bool(_tokens(text) & NEGATION_TERMS)


@dataclass(frozen=True)
class ClaimSupportResult:
    claim: str
    status: ClaimSupportStatus
    supported: bool
    evidence_count: int
    best_evidence_index: int | None = None
    confidence: float = 0.0
    supporting_terms: tuple[str, ...] = ()
    source_trace: dict[str, Any] | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "status": self.status,
            "supported": self.supported,
            "evidence_count": self.evidence_count,
            "best_evidence_index": self.best_evidence_index,
            "confidence": self.confidence,
            "supporting_terms": list(self.supporting_terms),
            "source_trace": self.source_trace or {},
            "message": self.message,
        }


class ClaimSupportVerifier:
    """Classify whether a claim is supported by admitted evidence/source text.

    This is a deterministic verifier baseline. It does not claim legal entailment
    quality yet; it supplies explicit statuses that block filing-ready export until
    stronger claim-support verification or human review is complete.
    """

    def verify(
        self,
        claim: str,
        evidence_chunks: Iterable[str],
        *,
        authority_statuses: Iterable[str] | None = None,
        expected_jurisdiction: str = "maine",
        source_jurisdictions: Iterable[str] | None = None,
        source_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        return self.verify_claim(
            claim,
            evidence_chunks,
            authority_statuses=authority_statuses,
            expected_jurisdiction=expected_jurisdiction,
            source_jurisdictions=source_jurisdictions,
            source_ids=source_ids,
        ).to_dict()

    def verify_claim(
        self,
        claim: str,
        evidence_chunks: Iterable[str],
        *,
        authority_statuses: Iterable[str] | None = None,
        expected_jurisdiction: str = "maine",
        source_jurisdictions: Iterable[str] | None = None,
        source_ids: Iterable[str] | None = None,
    ) -> ClaimSupportResult:
        chunks = [chunk for chunk in evidence_chunks if chunk and chunk.strip()]
        source_id_list = [str(source_id) for source_id in (source_ids or [])]
        if not claim.strip() or not chunks:
            return ClaimSupportResult(
                claim=claim,
                status="not_verifiable",
                supported=False,
                evidence_count=len(chunks),
                message="claim or evidence was empty",
            )

        jurisdictions = {jurisdiction.lower() for jurisdiction in (source_jurisdictions or [])}
        if jurisdictions and expected_jurisdiction.lower() not in jurisdictions and "federal" not in jurisdictions:
            return ClaimSupportResult(
                claim=claim,
                status="jurisdiction_mismatch",
                supported=False,
                evidence_count=len(chunks),
                message="evidence jurisdiction does not match the expected jurisdiction",
            )

        statuses = {status.lower() for status in (authority_statuses or [])}
        if statuses & {"stale", "stale_unknown", "overruled_or_negative_treatment_unknown"}:
            return ClaimSupportResult(
                claim=claim,
                status="stale",
                supported=False,
                evidence_count=len(chunks),
                message="supporting authority has stale or unresolved authority status",
            )

        claim_tokens = _tokens(claim)
        if not claim_tokens:
            return ClaimSupportResult(
                claim=claim,
                status="not_verifiable",
                supported=False,
                evidence_count=len(chunks),
                message="claim contained no verifiable terms",
            )

        best_index: int | None = None
        best_overlap = 0.0
        best_terms: set[str] = set()
        claim_negated = _has_negation(claim)
        contradicted = False

        for index, chunk in enumerate(chunks):
            chunk_tokens = _tokens(chunk)
            terms = claim_tokens & chunk_tokens
            overlap = len(terms) / max(len(claim_tokens), 1)
            if overlap > best_overlap:
                best_overlap = overlap
                best_index = index
                best_terms = terms
            if overlap >= 0.45 and claim_negated != _has_negation(chunk):
                contradicted = True

        if contradicted:
            return ClaimSupportResult(
                claim=claim,
                status="contradicted",
                supported=False,
                evidence_count=len(chunks),
                best_evidence_index=best_index,
                confidence=round(best_overlap, 4),
                supporting_terms=tuple(sorted(best_terms)),
                source_trace=_source_trace(source_id_list, best_index, best_terms),
                message="similar evidence appears to contradict the claim polarity",
            )
        if best_overlap >= 0.72:
            status: ClaimSupportStatus = "supported"
            supported = True
        elif best_overlap >= 0.38:
            status = "partially_supported"
            supported = False
        else:
            status = "unsupported"
            supported = False

        return ClaimSupportResult(
            claim=claim,
            status=status,
            supported=supported,
            evidence_count=len(chunks),
            best_evidence_index=best_index,
            confidence=round(best_overlap, 4),
            supporting_terms=tuple(sorted(best_terms)),
            source_trace=_source_trace(source_id_list, best_index, best_terms),
            message=f"claim classified as {status}",
        )


def _source_trace(source_ids: list[str], best_index: int | None, terms: set[str]) -> dict[str, Any]:
    source_id = None
    if best_index is not None and 0 <= best_index < len(source_ids):
        source_id = source_ids[best_index]
    elif source_ids:
        source_id = source_ids[0]
    return {
        "best_source_id": source_id,
        "best_evidence_index": best_index,
        "matched_terms": sorted(terms),
    }
