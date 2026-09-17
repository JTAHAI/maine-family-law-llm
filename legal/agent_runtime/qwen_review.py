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


def verify_qwen_excerpts(excerpts, sources, *, task="evidence_review"):
    from legal.fast_interchange.evidence_output import verify_selected_evidence_spans

    rows = []
    for item in excerpts:
        reference, quote = item["reference"], item["quote"]
        if not 1 <= reference <= len(sources):
            raise ValueError("unknown_source")
        source = sources[reference - 1]
        start = source.text.find(quote)
        if start < 0:
            raise ValueError("quote_not_in_record")
        rows.append(
            {
                "source_id": source.source_id,
                "reference": reference,
                "start_offset": start,
                "end_offset": start + len(quote),
                "source_text_sha256": sha256(source.text.encode()).hexdigest(),
                "quote_sha256": sha256(quote.encode()).hexdigest(),
                "status": "exact",
            }
        )
    report = verify_selected_evidence_spans(tuple(rows), sources)
    if task == "drafting":
        from .contracts import canonical_json

        report.update(schema_version="drafting_output_boundary_v1", filing_ready=False)
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
