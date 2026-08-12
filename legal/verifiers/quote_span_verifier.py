from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Literal

QuoteStatus = Literal["exact_match", "fuzzy_match", "semantic_match", "quote_span_not_found"]


def _normalize_text(text: str) -> str:
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    return re.sub(r"\s+", " ", text.strip()).lower()


def _token_set(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9][a-z0-9-]*", _normalize_text(text)) if len(token) > 2}


@dataclass(frozen=True)
class QuoteVerification:
    quoted_text: str
    status: QuoteStatus
    verified: bool
    quote_span_found: bool
    start_offset: int | None = None
    end_offset: int | None = None
    confidence: float = 0.0
    method: str = "exact"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "quoted_text": self.quoted_text,
            "status": self.status,
            "verified": self.verified,
            "quote_span_found": self.quote_span_found,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": self.confidence,
            "method": self.method,
            "message": self.message,
        }


class QuoteSpanVerifier:
    """Verify that a quote exists in a cited source.

    Exact source matching is preferred. Fuzzy matching is intentionally conservative
    and returns a separate status so filing gates can decide whether exact or fuzzy is
    acceptable for the requested export.
    """

    def __init__(self, *, fuzzy_threshold: float = 0.88, semantic_threshold: float = 0.72) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold

    def verify(self, source_text: str, quoted_text: str) -> dict[str, Any]:
        return self.verify_span(source_text, quoted_text).to_dict()

    def verify_span(self, source_text: str, quoted_text: str) -> QuoteVerification:
        source = source_text or ""
        quote = (quoted_text or "").strip()
        if not source.strip() or not quote:
            return QuoteVerification(
                quoted_text=quoted_text,
                status="quote_span_not_found",
                verified=False,
                quote_span_found=False,
                method="input_validation",
                message="source text or quoted text was empty",
            )

        exact_start = source.find(quote)
        if exact_start >= 0:
            return QuoteVerification(
                quoted_text=quoted_text,
                status="exact_match",
                verified=True,
                quote_span_found=True,
                start_offset=exact_start,
                end_offset=exact_start + len(quote),
                confidence=1.0,
                method="exact",
                message="quote found exactly in source",
            )

        normalized_source = _normalize_text(source)
        normalized_quote = _normalize_text(quote)
        normalized_start = normalized_source.find(normalized_quote)
        if normalized_start >= 0:
            return QuoteVerification(
                quoted_text=quoted_text,
                status="fuzzy_match",
                verified=True,
                quote_span_found=True,
                confidence=0.95,
                method="normalized_whitespace",
                message="quote found after whitespace and punctuation normalization",
            )

        best_ratio = 0.0
        words = normalized_source.split()
        quote_word_count = max(len(normalized_quote.split()), 1)
        window_sizes = sorted({quote_word_count, quote_word_count + 2, max(quote_word_count - 2, 1)})
        for window_size in window_sizes:
            for start in range(0, max(len(words) - window_size + 1, 1)):
                window = " ".join(words[start : start + window_size])
                ratio = SequenceMatcher(None, normalized_quote, window).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio

        if best_ratio >= self.fuzzy_threshold:
            return QuoteVerification(
                quoted_text=quoted_text,
                status="fuzzy_match",
                verified=True,
                quote_span_found=True,
                confidence=round(best_ratio, 4),
                method="sequence_similarity",
                message="quote closely matched source text but not exactly",
            )

        source_tokens = _token_set(source)
        quote_tokens = _token_set(quote)
        overlap = len(source_tokens & quote_tokens) / max(len(quote_tokens), 1)
        if quote_tokens and overlap >= self.semantic_threshold and len(quote_tokens) >= 4:
            return QuoteVerification(
                quoted_text=quoted_text,
                status="semantic_match",
                verified=True,
                quote_span_found=True,
                confidence=round(overlap, 4),
                method="token_overlap",
                message="quote terms are substantially present but not as an exact span",
            )

        return QuoteVerification(
            quoted_text=quoted_text,
            status="quote_span_not_found",
            verified=False,
            quote_span_found=False,
            confidence=round(max(best_ratio, overlap), 4),
            method="not_found",
            message="quote span was not found in the cited source",
        )
