from __future__ import annotations

import hashlib
import re
import unicodedata
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

NEGATION_TERMS = {"not", "no", "never", "cannot", "without", "insufficient", "lacks", "lack", "prohibited"}
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "must", "shall", "may", "are", "was", "were",
    "has", "have", "into", "under", "according", "maine", "court", "courts", "law", "laws", "a", "an", "to",
    "of", "in", "on", "at", "by", "or", "as", "it", "its", "be", "is", "can", "will", "would", "should",
}
LEGAL_CLAIM_TRIGGERS = {
    "must", "shall", "may", "requires", "required", "prohibits", "standard", "findings", "best interest",
    "parental rights", "support", "custody", "jurisdiction", "deadline", "file", "appeal", "contempt", "order",
}
_MAX_CHUNKS = 128
_MAX_CHUNK_CHARS = 100_000
_MAX_SENTENCES_PER_CHUNK = 1000


def extract_legal_claims(text: str) -> list[str]:
    """Extract candidate legal assertions conservatively and deterministically."""
    claims: list[str] = []
    seen: set[str] = set()
    normalized = (text or "").replace("\r\n", "\n")
    for _start, _end, sentence in _sentence_spans(normalized.strip()):
        cleaned = re.sub(r"\s+", " ", sentence).strip(" \t\n-*•")
        if len(cleaned) < 12 or len(cleaned) > 4000:
            continue
        lowered = cleaned.lower()
        if (
            any(trigger in lowered for trigger in LEGAL_CLAIM_TRIGGERS)
            or re.search(r"\b\d+(?:-[A-Z])?\s*M\.?R\.?S\.?A?\.?\s*§", cleaned, re.I)
            or re.search(r"\b\d{4}\s+ME\s+\d+\b", cleaned)
            or re.search(r"\bM\.R\.\s*(?:Civ|App|Evid)\.\s*P\.", cleaned, re.I)
        ):
            key = _normalize_text(cleaned)
            if key not in seen:
                seen.add(key)
                claims.append(cleaned)
    return claims


def _normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    value = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", value)
    value = value.casefold()
    value = re.sub(r"[^a-z0-9§¶-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _token_list(text: str) -> list[str]:
    normalized = _normalize_text(text).replace("-", " ")
    return [
        token for token in re.findall(r"[a-z0-9§¶]+", normalized)
        if len(token) > 1 and token not in STOPWORDS
    ]


def _tokens(text: str) -> set[str]:
    return set(_token_list(text))


def _has_negation(text: str) -> bool:
    return bool(_tokens(text) & NEGATION_TERMS)


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Return bounded sentence-like spans without splitting legal abbreviations.

    A boundary requires terminal punctuation followed by whitespace and an
    uppercase letter, or a blank-line break/end of text. This keeps citations
    such as ``M.R.S. § 1653`` in one span.
    """
    value = text or ""
    spans: list[tuple[int, int, str]] = []
    start = 0
    boundary = re.compile(r"(?<=[.!?])(?=\s+[A-Z])|(?=\n{2,})|$")
    for match in boundary.finditer(value):
        end = match.start()
        raw = value[start:end]
        stripped = raw.strip()
        if stripped:
            leading = len(raw) - len(raw.lstrip())
            item_start = start + leading
            item_end = item_start + len(stripped)
            spans.append((item_start, item_end, stripped))
            if len(spans) >= _MAX_SENTENCES_PER_CHUNK:
                break
        if match.start() == match.end() and match.start() == len(value):
            break
        start = match.start()
        while start < len(value) and value[start].isspace():
            start += 1
    if not spans and value:
        spans.append((0, min(len(value), _MAX_CHUNK_CHARS), value[:_MAX_CHUNK_CHARS]))
    return spans


def _numbers_and_citations(text: str) -> set[str]:
    return set(re.findall(r"\b(?:\d{4}\s+ME\s+\d+|\d+(?:-[A-Z])?\s*M\.?R\.?S\.?A?\.?\s*§?\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?)\b", text or "", re.I))


@dataclass(frozen=True)
class EvidenceCandidate:
    source_id: str | None
    evidence_index: int
    start_offset: int
    end_offset: int
    text: str
    score: float
    token_coverage: float
    matched_terms: tuple[str, ...]
    polarity_conflict: bool
    exact_phrase: bool
    required_numbers_matched: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "evidence_index": self.evidence_index,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "text": self.text,
            "score": round(self.score, 4),
            "token_coverage": round(self.token_coverage, 4),
            "matched_terms": list(self.matched_terms),
            "polarity_conflict": self.polarity_conflict,
            "exact_phrase": self.exact_phrase,
            "required_numbers_matched": self.required_numbers_matched,
        }


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
    best_span: dict[str, Any] | None = None
    candidate_sources: tuple[dict[str, Any], ...] = ()
    claim_sha256: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "claim_sha256": self.claim_sha256 or hashlib.sha256(self.claim.encode("utf-8")).hexdigest(),
            "status": self.status,
            "supported": self.supported,
            "evidence_count": self.evidence_count,
            "best_evidence_index": self.best_evidence_index,
            "confidence": self.confidence,
            "supporting_terms": list(self.supporting_terms),
            "source_trace": self.source_trace or {},
            "best_span": self.best_span or {},
            "candidate_sources": list(self.candidate_sources),
            "message": self.message,
        }


class ClaimSupportVerifier:
    """Deterministic claim-to-source matcher with exact source-span receipts.

    This is a conservative lexical verifier, not a legal-entailment model. It is
    designed to fail closed and provide a reproducible span for human review.
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
        source_classes: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        return self.verify_claim(
            claim,
            evidence_chunks,
            authority_statuses=authority_statuses,
            expected_jurisdiction=expected_jurisdiction,
            source_jurisdictions=source_jurisdictions,
            source_ids=source_ids,
            source_classes=source_classes,
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
        source_classes: Iterable[str] | None = None,
    ) -> ClaimSupportResult:
        chunks = [str(chunk)[:_MAX_CHUNK_CHARS] for chunk in evidence_chunks if str(chunk).strip()][:_MAX_CHUNKS]
        source_id_list = [str(source_id) for source_id in (source_ids or [])][:_MAX_CHUNKS]
        source_class_list = [str(value) for value in (source_classes or [])][:_MAX_CHUNKS]
        claim_hash = hashlib.sha256((claim or "").encode("utf-8")).hexdigest()
        if not claim.strip() or not chunks:
            return ClaimSupportResult(claim, "not_verifiable", False, len(chunks), claim_sha256=claim_hash, message="claim or evidence was empty")

        jurisdictions = {str(j).lower() for j in (source_jurisdictions or []) if j}
        if jurisdictions and expected_jurisdiction.lower() not in jurisdictions and "federal" not in jurisdictions:
            return ClaimSupportResult(claim, "jurisdiction_mismatch", False, len(chunks), claim_sha256=claim_hash, message="evidence jurisdiction does not match the expected jurisdiction")

        statuses = {str(status).lower() for status in (authority_statuses or []) if status}
        if statuses & {"stale", "stale_unknown", "stale_or_superseded", "superseded", "overruled_or_negative_treatment_unknown"}:
            return ClaimSupportResult(claim, "stale", False, len(chunks), claim_sha256=claim_hash, message="supporting authority has stale or unresolved authority status")

        claim_tokens = _tokens(claim)
        if not claim_tokens:
            return ClaimSupportResult(claim, "not_verifiable", False, len(chunks), claim_sha256=claim_hash, message="claim contained no verifiable terms")

        claim_norm = _normalize_text(claim)
        claim_numbers = _numbers_and_citations(claim)
        claim_negated = _has_negation(claim)
        candidates: list[EvidenceCandidate] = []
        for chunk_index, chunk in enumerate(chunks):
            source_id = source_id_list[chunk_index] if chunk_index < len(source_id_list) else None
            spans = _sentence_spans(chunk)
            # Review both individual sentences and a bounded two-sentence window.
            # Legal citations commonly appear in the sentence immediately before
            # the proposition they support.
            windows: list[tuple[int, int, str]] = []
            for span_index, (start, end, sentence) in enumerate(spans):
                windows.append((start, end, sentence))
                if span_index + 1 < len(spans):
                    next_start, next_end, _next_sentence = spans[span_index + 1]
                    windows.append((start, next_end, chunk[start:next_end].strip()))
            for start, end, sentence in windows:
                sentence_tokens = _tokens(sentence)
                matched = claim_tokens & sentence_tokens
                coverage = len(matched) / max(len(claim_tokens), 1)
                sentence_norm = _normalize_text(sentence)
                exact_phrase = bool(len(claim_norm) >= 18 and claim_norm in sentence_norm)
                number_match = not claim_numbers or claim_numbers.issubset(_numbers_and_citations(sentence))
                polarity_conflict = coverage >= 0.35 and claim_negated != _has_negation(sentence)
                score = coverage
                if exact_phrase:
                    score += 0.25
                if number_match and claim_numbers:
                    score += 0.12
                elif claim_numbers and not number_match:
                    score -= 0.20
                if polarity_conflict:
                    score -= 0.18
                if chunk_index < len(source_class_list) and "index" in source_class_list[chunk_index].lower():
                    score -= 0.03
                candidates.append(EvidenceCandidate(
                    source_id=source_id,
                    evidence_index=chunk_index,
                    start_offset=start,
                    end_offset=end,
                    text=sentence[:1600],
                    score=max(0.0, min(score, 1.0)),
                    token_coverage=coverage,
                    matched_terms=tuple(sorted(matched)),
                    polarity_conflict=polarity_conflict,
                    exact_phrase=exact_phrase,
                    required_numbers_matched=number_match,
                ))

        candidates.sort(
            key=lambda row: (
                -row.score,
                -row.token_coverage,
                row.end_offset - row.start_offset,
                row.evidence_index,
                row.start_offset,
            )
        )
        best = candidates[0] if candidates else None
        contradictory = next((row for row in candidates if row.polarity_conflict and row.token_coverage >= 0.55), None)
        if contradictory and (best is None or contradictory.token_coverage >= best.token_coverage - 0.05):
            return self._result(claim, claim_hash, "contradicted", False, chunks, contradictory, candidates, "the closest admitted source span appears to conflict with the claim polarity")
        if best is None:
            return ClaimSupportResult(claim, "not_verifiable", False, len(chunks), claim_sha256=claim_hash, message="no bounded source span was available")

        if best.score >= 0.72 and best.token_coverage >= 0.62 and best.required_numbers_matched:
            status: ClaimSupportStatus = "supported"
            supported = True
        elif best.score >= 0.45 and best.token_coverage >= 0.35:
            status = "partially_supported"
            supported = False
        else:
            status = "unsupported"
            supported = False
        return self._result(claim, claim_hash, status, supported, chunks, best, candidates, f"claim classified as {status}; human legal review remains required")

    @staticmethod
    def _result(
        claim: str,
        claim_hash: str,
        status: ClaimSupportStatus,
        supported: bool,
        chunks: list[str],
        best: EvidenceCandidate,
        candidates: list[EvidenceCandidate],
        message: str,
    ) -> ClaimSupportResult:
        top = tuple(row.to_dict() for row in candidates[:5])
        source_trace = {
            "best_source_id": best.source_id,
            "best_evidence_index": best.evidence_index,
            "matched_terms": list(best.matched_terms),
            "start_offset": best.start_offset,
            "end_offset": best.end_offset,
        }
        return ClaimSupportResult(
            claim=claim,
            status=status,
            supported=supported,
            evidence_count=len(chunks),
            best_evidence_index=best.evidence_index,
            confidence=round(best.score, 4),
            supporting_terms=best.matched_terms,
            source_trace=source_trace,
            best_span=best.to_dict(),
            candidate_sources=top,
            claim_sha256=claim_hash,
            message=message,
        )
