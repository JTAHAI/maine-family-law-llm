"""Deterministic quotation boundary, not a legal/factual truth classifier.

Only approved record bodies can substantiate a quotation. Prompt metadata,
the user's question and a numbered reference alone are never evidence.
"""

from __future__ import annotations

import re
from hashlib import sha256

from legal.agent_runtime.contracts import ContextSource, canonical_json
from legal.verifiers.citation_parser import extract_citations

_REFERENCE = re.compile(r"\[(\d+)\]")
_QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')


def _span(quote: str, body: str) -> tuple[int, int] | None:
    """Allow whitespace differences only; return offsets in the original body."""
    parts = re.split(r"\s+", quote.strip())
    if not parts or not any(parts):
        return None
    match = re.search(r"\s+".join(re.escape(part) for part in parts), body)
    return (match.start(), match.end()) if match else None


def verify_evidence_output(answer: str, sources: tuple[ContextSource, ...]) -> dict:
    blockers: list[str] = []
    refs = [int(value) for value in _REFERENCE.findall(answer)]
    if not sources or not refs or any(ref < 1 or ref > len(sources) for ref in refs):
        blockers.append("specialist_source_references_required")
    if any(source.lane != "private_record" for source in sources):
        blockers.append("evidence_review_private_records_required")
    spans = []
    quotes = list(_QUOTE.finditer(answer))
    if not quotes:
        blockers.append("evidence_review_exact_quote_required")
    # An unmatched quote is not silently ignored while other quotations pass.
    remainder = _QUOTE.sub("", answer)
    if any(delimiter in remainder for delimiter in ('"', '“', '”')):
        blockers.append("evidence_review_malformed_quote")
    for quote in quotes:
        text = quote.group(1) or quote.group(2)
        # Citation must follow this quotation, not another sentence or quote.
        following = re.match(r"[\s.,;:]*\[(\d+)\]", answer[quote.end():])
        index = int(following.group(1)) if following else 0
        source = sources[index - 1] if 1 <= index <= len(sources) else None
        span = _span(text, source.text) if source else None
        if span is None:
            blockers.append("evidence_review_quote_not_in_cited_record")
        else:
            spans.append({
                "source_id": source.source_id, "reference": index,
                "start_offset": span[0], "end_offset": span[1],
                "source_text_sha256": sha256(source.text.encode("utf-8")).hexdigest(),
                "quote_sha256": sha256(text.encode("utf-8")).hexdigest(),
                "status": "exact" if text in source.text else "whitespace_normalized",
            })
    # Evidence Review cannot introduce law. Even an existing citation is only
    # acceptable as quoted record content, never as this specialist's authority.
    for citation in extract_citations(answer):
        if not any(q.start() < citation.start and q.end() > citation.end for q in quotes):
            blockers.append("evidence_review_legal_authority_not_verified")
    report = {
        "schema_version": "evidence_output_boundary_v1",
        "status": "withheld" if blockers else "quoted_spans_bound_review_required",
        "display_mode": "withheld" if blockers else "verified_extracts_only",
        "review_required": True,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "source_spans": spans,
        "blockers": sorted(set(blockers)),
        "candidate_answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
    }
    report["report_sha256"] = sha256(canonical_json(report)).hexdigest()
    return report


def render_verified_evidence_extracts(report: dict, sources: tuple[ContextSource, ...]) -> str:
    """Display only checked body spans, never the candidate's unchecked prose.

    This is an explicitly extractive mode. Passing quotation checks is not
    enough to establish that the narrative around a quotation is supported.
    """
    if report.get("blockers") or not report.get("source_spans"):
        raise ValueError("evidence_review_no_verified_extracts")
    extracts = []
    seen = set()
    for span in report["source_spans"]:
        index, start, end = span["reference"], span["start_offset"], span["end_offset"]
        source = sources[index - 1]
        if (source.source_id != span["source_id"] or not 0 <= start < end <= len(source.text)
                or sha256(source.text.encode("utf-8")).hexdigest() != span["source_text_sha256"]):
            raise ValueError("evidence_review_source_changed")
        key = (index, start, end)
        if key not in seen:
            # These are literal source characters, not regenerated quotations.
            extracts.append(f'"{source.text[start:end]}" [{index}]')
            seen.add(key)
    return (
        "Evidence Review — model-selected record excerpts\n\n"
        + "\n\n".join(extracts)
        + "\n\nThese excerpts match the approved records. The model's other narrative "
        "was withheld because its factual conclusions were not verified. Open each source "
        "to check surrounding context, differences, and missing information. A record's "
        "statement is not an established fact.\n\nReview required."
    )
