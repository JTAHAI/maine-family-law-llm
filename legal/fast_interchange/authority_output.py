"""Exact-span boundary for optional local Maine authority review.

This module does not determine current law, jurisdiction, controlling weight,
or how authority applies to a family.  It permits a local model only to select
literal passages from an active, host-verified official Maine authority product.
Every source and freshness check is repeated by the host before display.
"""

from __future__ import annotations

import hmac
from hashlib import sha256

from legal.agent_runtime.contracts import ContextSource, canonical_json
from legal.verifiers.authority_status_verifier import is_official_maine_https_url


def _is_admitted_official_maine_source(source: ContextSource) -> bool:
    """Require the authority service's immutable-source marker, not model text."""

    return (
        source.lane == "legal_authority"
        and str(source.authority_status or "").startswith("verified_immutable_source_")
        and str(source.freshness_status or "").casefold() == "fresh"
        and str((source.metadata or {}).get("jurisdiction") or "").casefold() == "maine"
        and is_official_maine_https_url(
            str((source.metadata or {}).get("official_source_url") or "")
        )
    )


def verify_selected_authority_spans(
    rows: tuple[dict, ...], sources: tuple[ContextSource, ...]
) -> dict:
    """Fail closed unless every approved source contributes an exact fresh span."""

    blockers: list[str] = []
    spans: list[dict] = []
    represented: set[int] = set()
    keys = {
        "source_id",
        "reference",
        "start_offset",
        "end_offset",
        "source_text_sha256",
        "quote_sha256",
        "status",
    }
    if not isinstance(rows, tuple) or not 1 <= len(rows) <= 24:
        blockers.append("authority_review_selected_spans_invalid")
    if not sources or any(not _is_admitted_official_maine_source(source) for source in sources):
        blockers.append("authority_review_official_fresh_maine_sources_required")

    for row in rows if isinstance(rows, tuple) else ():
        if not isinstance(row, dict) or set(row) != keys:
            blockers.append("authority_review_selected_spans_invalid")
            continue
        index, start, end = row["reference"], row["start_offset"], row["end_offset"]
        if (
            any(type(value) is not int for value in (index, start, end))
            or not 1 <= index <= len(sources)
        ):
            blockers.append("authority_review_selected_spans_invalid")
            continue
        source = sources[index - 1]
        if (
            not _is_admitted_official_maine_source(source)
            or not 0 <= start < end <= len(source.text)
            or end - start > 1200
            or row["source_id"] != source.source_id
            or row["status"] != "exact"
            or row["source_text_sha256"] != sha256(source.text.encode("utf-8")).hexdigest()
            or row["quote_sha256"] != sha256(source.text[start:end].encode("utf-8")).hexdigest()
        ):
            blockers.append("authority_review_selected_source_changed")
            continue
        key = (index, start, end)
        if key in {(item["reference"], item["start_offset"], item["end_offset"]) for item in spans}:
            blockers.append("authority_review_selected_spans_invalid")
            continue
        represented.add(index)
        spans.append(dict(row))

    if represented != set(range(1, len(sources) + 1)):
        blockers.append("authority_review_all_selected_sources_required")
    report = {
        "schema_version": "authority_selected_spans_boundary_v1",
        "status": "withheld" if blockers else "official_spans_bound_review_required",
        "display_mode": "withheld" if blockers else "official_authority_extracts_only",
        "review_required": True,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "current_law_determined": False,
        "source_spans": [] if blockers else spans,
        "blockers": sorted(set(blockers)),
    }
    report["report_sha256"] = sha256(canonical_json(report)).hexdigest()
    return report


def render_verified_authority_extracts(report: dict, sources: tuple[ContextSource, ...]) -> str:
    """Render only rechecked official-source characters and host-owned cautions."""

    if not isinstance(report, dict):
        raise ValueError("authority_review_report_invalid")
    expected = sha256(
        canonical_json({key: value for key, value in report.items() if key != "report_sha256"})
    ).hexdigest()
    if not isinstance(report.get("report_sha256"), str) or not hmac.compare_digest(
        expected, report["report_sha256"]
    ):
        raise ValueError("authority_review_report_invalid")
    if (
        report.get("schema_version") != "authority_selected_spans_boundary_v1"
        or report.get("status") != "official_spans_bound_review_required"
        or report.get("review_required") is not True
        or report.get("legal_claims_verified") is not False
        or report.get("current_law_determined") is not False
        or report.get("blockers")
        or not report.get("source_spans")
        or any(not _is_admitted_official_maine_source(source) for source in sources)
    ):
        raise ValueError("authority_review_report_invalid")
    extracts: list[str] = []
    seen: set[tuple[int, int, int]] = set()
    for span in report["source_spans"]:
        index, start, end = span.get("reference"), span.get("start_offset"), span.get("end_offset")
        if (
            any(type(value) is not int for value in (index, start, end))
            or not 1 <= index <= len(sources)
        ):
            raise ValueError("authority_review_source_changed")
        source = sources[index - 1]
        if (
            not _is_admitted_official_maine_source(source)
            or span.get("source_id") != source.source_id
            or not 0 <= start < end <= len(source.text)
            or span.get("source_text_sha256") != sha256(source.text.encode("utf-8")).hexdigest()
            or span.get("quote_sha256") != sha256(source.text[start:end].encode("utf-8")).hexdigest()
        ):
            raise ValueError("authority_review_source_changed")
        key = (index, start, end)
        if key not in seen:
            extracts.append(f'{source.title} — "{source.text[start:end]}" [{index}]')
            seen.add(key)
    return (
        "Maine Authority Review — exact official-source passages\n\n"
        + "\n\n".join(extracts)
        + "\n\nThese passages match the selected current official Maine sources. They do not "
        "determine current law, jurisdiction, controlling weight, applicability, or a legal outcome. "
        "Open each source card to inspect its citation, freshness, complete text, and provenance.\n\n"
        "Review required."
    )
