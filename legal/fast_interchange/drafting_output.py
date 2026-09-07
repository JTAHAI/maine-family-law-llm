"""Fail-closed boundary for the local Drafting specialist.

The model may select exact private-record excerpts.  It may not author the
user-visible factual narrative: the host renders a deliberately narrow working
draft from rechecked source spans.  This prevents fluent unsupported prose from
being mistaken for a verified fact or filing-ready work product.
"""

from __future__ import annotations

import re
from hashlib import sha256

from legal.agent_runtime.contracts import ContextSource, canonical_json
from legal.security.protected_spans import overlaps_protected_span
from legal.verifiers.citation_parser import extract_citations

_REFERENCE = re.compile(r"\[(\d+)\]")
_QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')


def _span(quote: str, body: str) -> tuple[int, int] | None:
    parts = re.split(r"\s+", quote.strip())
    if not parts or not any(parts):
        return None
    match = re.search(r"\s+".join(re.escape(part) for part in parts), body)
    return (match.start(), match.end()) if match else None


def verify_drafting_output(answer: str, sources: tuple[ContextSource, ...]) -> dict:
    """Bind every selected excerpt to a private record and return offsets."""

    blockers: list[str] = []
    refs = [int(value) for value in _REFERENCE.findall(answer)]
    if not sources or not refs or any(ref < 1 or ref > len(sources) for ref in refs):
        blockers.append("specialist_source_references_required")
    if any(source.lane != "private_record" for source in sources):
        blockers.append("drafting_private_record_sources_required")
    quotes = list(_QUOTE.finditer(answer))
    if not quotes:
        blockers.append("drafting_exact_quote_required")
    remainder = _QUOTE.sub("", answer)
    if any(delimiter in remainder for delimiter in ('"', "“", "”")):
        blockers.append("drafting_malformed_quote")

    spans: list[dict] = []
    suppressed_spans: list[dict] = []
    for quote in quotes:
        text = quote.group(1) or quote.group(2)
        following = re.match(r"[\s.,;:]*\[(\d+)\]", answer[quote.end() :])
        index = int(following.group(1)) if following else 0
        source = sources[index - 1] if 1 <= index <= len(sources) else None
        located = _span(text, source.text) if source else None
        if located is None:
            blockers.append("drafting_quote_not_in_cited_record")
        elif overlaps_protected_span(located[0], located[1], source.text, source.metadata):
            blockers.append("drafting_sensitive_quote_withheld")
            suppressed_spans.append(
                {
                    "source_id": source.source_id,
                    "reference": index,
                    "start_offset": located[0],
                    "end_offset": located[1],
                    "reason": "labeled_sensitive_value",
                }
            )
        else:
            spans.append(
                {
                    "source_id": source.source_id,
                    "reference": index,
                    "start_offset": located[0],
                    "end_offset": located[1],
                    "source_text_sha256": sha256(source.text.encode("utf-8")).hexdigest(),
                    "quote_sha256": sha256(text.encode("utf-8")).hexdigest(),
                    "status": "exact" if text in source.text else "whitespace_normalized",
                }
            )
    for citation in extract_citations(answer):
        if not any(
            quote.start() < citation.start and quote.end() > citation.end for quote in quotes
        ):
            blockers.append("drafting_legal_authority_not_verified")
    # An omitted selected record may be the contradiction that changes the
    # working draft. Require one verified or deliberately suppressed span from
    # each record before showing any model-selected working material.
    represented = {row["reference"] for row in (*spans, *suppressed_spans)}
    if sources and represented != set(range(1, len(sources) + 1)):
        blockers.append("drafting_all_records_required")

    unique_blockers = sorted(set(blockers))
    partial_extracts_available = (
        bool(spans)
        and bool(unique_blockers)
        and set(unique_blockers).issubset(
            {"drafting_quote_not_in_cited_record", "drafting_sensitive_quote_withheld"}
        )
    )
    report = {
        "schema_version": "drafting_output_boundary_v1",
        "status": (
            "partial_quoted_spans_bound_review_required"
            if unique_blockers and partial_extracts_available
            else "withheld"
            if unique_blockers
            else "quoted_spans_bound_review_required"
        ),
        "display_mode": (
            "source_bound_draft_extracts_partial"
            if unique_blockers and partial_extracts_available
            else "withheld"
            if unique_blockers
            else "source_bound_draft_extracts_only"
        ),
        "review_required": True,
        "filing_ready": False,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "source_spans": spans,
        "suppressed_spans": suppressed_spans,
        "partial_extracts_available": partial_extracts_available,
        "blockers": unique_blockers,
        "candidate_answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
    }
    report["report_sha256"] = sha256(canonical_json(report)).hexdigest()
    return report


def render_source_bound_draft(
    report: dict,
    sources: tuple[ContextSource, ...],
    *,
    allow_partial: bool = False,
) -> str:
    """Render only literal, rechecked record text plus host-owned cautions."""

    if (report.get("blockers") and not allow_partial) or not report.get("source_spans"):
        raise ValueError("drafting_no_verified_extracts")
    if allow_partial and not report.get("partial_extracts_available"):
        raise ValueError("drafting_no_verified_partial_extracts")
    extracts: list[str] = []
    seen: set[tuple[int, int, int]] = set()
    for span in report["source_spans"]:
        index, start, end = span["reference"], span["start_offset"], span["end_offset"]
        source = sources[index - 1]
        if (
            source.source_id != span["source_id"]
            or not 0 <= start < end <= len(source.text)
            or sha256(source.text.encode("utf-8")).hexdigest() != span["source_text_sha256"]
            or overlaps_protected_span(start, end, source.text, source.metadata)
        ):
            raise ValueError("drafting_source_changed")
        key = (index, start, end)
        if key not in seen:
            extracts.append(f'"{source.text[start:end]}" [{index}]')
            seen.add(key)
    partial_notice = (
        "\n\nSome model-selected text was withheld because it was inexact, sensitive, "
        "or otherwise failed verification."
        if report.get("blockers")
        else ""
    )
    return (
        "Drafting Assistant — source-bound working material\n\n"
        "The supplied records state:\n\n"
        + "\n\n".join(extracts)
        + partial_notice
        + "\n\nThis is a working extract, not a factual finding, legal conclusion, or "
        "filing-ready draft. The model's other prose was withheld. Open each source, "
        "check surrounding context, add missing support, and revise the wording before use."
        "\n\nReview required."
    )
