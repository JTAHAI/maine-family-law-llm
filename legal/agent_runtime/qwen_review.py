"""Narrow output checks for general Qwen reviews, not legal/factual validation."""

from __future__ import annotations

import re
from hashlib import sha256

_QUOTE = re.compile(r'["“]([^"“”\n]{4,1200})["”]')
_CITATION = re.compile(r"\[([0-9]{1,3})\]")
_LEGAL = re.compile(
    r"\b(?:\d{4}\s+ME\s+\d+|\d+[A-Z-]*\s+M\.?R\.?S\.?(?:A\.?)?\s*§?\s*\d+[A-Z-]*|M\.R\.(?:Civ|App|Crim)\.P\.\s*\d+)",
    re.I,
)


_BOUNDARY = re.compile(r"[.!?](?:[\"”')\]]*)\s+|\n{2,}")


def _contextual_span(text: str, start: int, end: int, *, limit: int = 1200) -> tuple[int, int]:
    """Expand a selected fragment to its full sentence/paragraph context.

    The model may select a useful short phrase. Rendering it alone can lose a
    negation or exception. The host therefore displays original surrounding
    context, never a shortened fragment that changes the source's meaning.
    """

    previous = [match.end() for match in _BOUNDARY.finditer(text, 0, start)]
    following = [match.start() + 1 for match in _BOUNDARY.finditer(text, end)]
    left = previous[-1] if previous else 0
    right = following[0] if following else len(text)
    while left < len(text) and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if right - left > limit:
        raise ValueError("contextual_quote_too_large")
    return left, right


def _unique_match(quote: str, text: str) -> tuple[int, int]:
    starts, offset = [], 0
    while True:
        match = text.find(quote, offset)
        if match < 0:
            break
        starts.append(match)
        offset = match + 1
    if not starts:
        raise ValueError("quote_not_in_record")
    if len(starts) != 1:
        raise ValueError("quote_ambiguous_in_record")
    return starts[0], starts[0] + len(quote)


def _verified_flags(flags, rows, sources):
    available = {row["reference"] for row in rows}
    allowed = {
        "possible_conflict", "possible_agreement", "missing_material",
        "proposal_not_acceptance", "qualification", "record_difference",
    }
    result = []
    for flag in flags:
        if not isinstance(flag, dict) or set(flag) != {"kind", "references"}:
            raise ValueError("review_flag_invalid")
        refs = tuple(flag["references"])
        if flag["kind"] not in allowed or not refs or len(set(refs)) != len(refs):
            raise ValueError("review_flag_invalid")
        if any(type(ref) is not int or ref not in available or not 1 <= ref <= len(sources) for ref in refs):
            raise ValueError("review_flag_unbound")
        result.append({"kind": flag["kind"], "references": list(refs), "status": "model_suggestion_review_required"})
    return result


def _verified_draft_sections(sections, rows, sources):
    """Accept only fixed host headings that point to verified extracts.

    A section is an organizing cue, not a factual assertion.  It is valid only
    after every referenced record has supplied a separately rechecked exact
    source span.  This deliberately keeps the model from drafting prose or
    smuggling a conclusion into a heading.
    """

    available = {row["reference"] for row in rows}
    allowed = {"background", "record_difference", "support_gaps", "requested_review"}
    result = []
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"heading", "references"}:
            raise ValueError("draft_section_invalid")
        refs = tuple(section["references"])
        if section["heading"] not in allowed or not refs or len(set(refs)) != len(refs):
            raise ValueError("draft_section_invalid")
        if any(type(ref) is not int or ref not in available or not 1 <= ref <= len(sources) for ref in refs):
            raise ValueError("draft_section_unbound")
        result.append(
            {
                "heading": section["heading"],
                "references": list(refs),
                "status": "model_organization_review_required",
            }
        )
    return result


def verify_qwen_excerpts(
    excerpts,
    sources,
    *,
    task="evidence_review",
    review_flags=(),
    draft_sections=(),
    coverage=(),
):
    rows = []
    for item in excerpts:
        reference, quote = item["reference"], item["quote"]
        if not 1 <= reference <= len(sources):
            raise ValueError("unknown_source")
        source = sources[reference - 1]
        start, end = _unique_match(quote, source.text)
        start, end = _contextual_span(source.text, start, end)
        displayed = source.text[start:end]
        rows.append(
            {
                "source_id": source.source_id,
                "reference": reference,
                "start_offset": start,
                "end_offset": end,
                "source_text_sha256": sha256(source.text.encode()).hexdigest(),
                "quote_sha256": sha256(displayed.encode()).hexdigest(),
                "status": "exact",
            }
        )
    if task == "authority_review":
        from legal.fast_interchange.authority_output import verify_selected_authority_spans

        report = verify_selected_authority_spans(tuple(rows), sources)
    else:
        from legal.fast_interchange.evidence_output import verify_selected_evidence_spans

        report = verify_selected_evidence_spans(
            tuple(rows),
            sources,
            coverage=tuple(coverage),
            # This is an explicit host-owned structured contract. The default
            # span verifier remains one-excerpt-per-record for legacy callers.
            allow_multiple_per_record=True,
        )
    if report["blockers"]:
        return report
    report["task_review_flags"] = _verified_flags(review_flags, rows, sources)
    report["relevance_verified"] = False
    if task == "drafting":
        report.update(
            schema_version="drafting_output_boundary_v1",
            filing_ready=False,
            task_outline_sections=_verified_draft_sections(draft_sections, rows, sources),
        )
    elif draft_sections:
        raise ValueError("draft_sections_unavailable")
    from .contracts import canonical_json

    report["report_sha256"] = sha256(
        canonical_json({key: value for key, value in report.items() if key != "report_sha256"})
    ).hexdigest()
    return report


def check_review(answer, sources, task):
    def normalize(value):
        return " ".join(value.split()).casefold()
    texts = [normalize(source.text) for source in sources]
    blockers = []
    refs = {int(value) for value in _CITATION.findall(answer)}
    if task == "evidence_review" and refs != set(range(1, len(sources) + 1)):
        blockers.append("qwen_review_selected_record_omitted")
    quotes = [
        match.group(1) for match in _QUOTE.finditer(answer) if len(match.group(1).split()) >= 4
    ]
    if any(not any(normalize(quote) in text for text in texts) for quote in quotes):
        blockers.append("qwen_review_quote_not_in_approved_context")
    if any(
        not any(normalize(match.group()) in text for text in texts)
        for match in _LEGAL.finditer(answer)
    ):
        blockers.append("qwen_review_legal_citation_not_in_context")
    return {
        "schema_version": "qwen_review_lexical_boundary_v1",
        "status": "blocked" if blockers else "lexical_checks_only_review_required",
        "blockers": blockers,
        "explicit_multiword_quotes_checked": len(quotes),
        "all_selected_records_referenced": refs == set(range(1, len(sources) + 1)),
        "quote_attribution_verified": False,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "review_required": True,
    }
