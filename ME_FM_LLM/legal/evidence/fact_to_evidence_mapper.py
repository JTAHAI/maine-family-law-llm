from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "with",
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS}


def _span_for(fact: str, evidence_text: str, fallback_start: int | None = None, fallback_end: int | None = None) -> tuple[int | None, int | None]:
    if fallback_start is not None and fallback_end is not None:
        return fallback_start, fallback_end
    start = evidence_text.lower().find(fact.lower())
    if start >= 0:
        return start, start + len(fact)
    fact_tokens = list(_tokens(fact))
    if not fact_tokens:
        return None, None
    first = fact_tokens[0]
    match = re.search(re.escape(first), evidence_text, re.IGNORECASE)
    if not match:
        return None, None
    return match.start(), min(len(evidence_text), match.end() + 160)


class FactToEvidenceMapper:
    def map(self, facts: list[str], evidence: list[dict[str, Any]]):
        mappings = []

        for index, fact in enumerate(facts):
            fact_tokens = _tokens(fact)
            supporting = []
            for item in evidence:
                evidence_text = item.get("text", "")
                evidence_tokens = _tokens(evidence_text)
                if not fact_tokens or not evidence_tokens:
                    continue
                overlap = len(fact_tokens & evidence_tokens)
                score = overlap / max(len(fact_tokens), 1)
                exact = fact.lower() in evidence_text.lower()
                if exact or score >= 0.35:
                    span_start, span_end = _span_for(
                        fact,
                        evidence_text,
                        item.get("span_start"),
                        item.get("span_end"),
                    )
                    support_score = round(1.0 if exact else score, 3)
                    supporting.append({
                        **item,
                        "source_document_id": item.get("source_document_id") or item.get("document_id"),
                        "span_start": span_start,
                        "span_end": span_end,
                        "confidence": round(float(item.get("confidence", support_score)) * support_score, 3),
                        "support_score": support_score,
                    })

            mappings.append({
                "fact_id": f"fact_{index}",
                "fact": fact,
                "supporting_evidence": sorted(
                    supporting,
                    key=lambda item: item.get("support_score", 0),
                    reverse=True,
                ),
                "support_status": "supported" if supporting else "unsupported",
                "review_required": True,
            })

        return mappings
