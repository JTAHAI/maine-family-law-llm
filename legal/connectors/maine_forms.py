from __future__ import annotations

import re

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import CourtForm, SourceLocation

PARSER_VERSION = "maine_forms_parser_v1"
_FORM_ID_RE = re.compile(r"\b(FM|PA|CV|PB)-?\s?(\d{3}[A-Z]?)\b", re.I)
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)
_VERSION_RE = re.compile(r"(?:Rev\.?|Revised|Version)\s*(?:date)?\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}/\d{4}|[A-Za-z]+\s+\d{4})", re.I)


def normalize_form_id(value: str) -> str:
    match = _FORM_ID_RE.search(value)
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{match.group(2).upper()}"


def parse_forms_index(html: str, *, source_id: str, url: str) -> tuple[list[CourtForm], ParserAuditEvent]:
    links, _visible_text = collect_links_and_text(html, base_url=url)
    forms: list[CourtForm] = []
    for link in links:
        href = link["href"]
        label = normalize_whitespace(link["text"])
        match = _FORM_ID_RE.search(label) or _FORM_ID_RE.search(href)
        if not match and not _PDF_RE.search(href):
            continue
        form_id = normalize_form_id(match.group(0)) if match else None
        document_id = stable_source_id("me-court-form", href)
        title = label or href.rsplit("/", 1)[-1]
        forms.append(
            CourtForm(
                document_id=document_id,
                source_location=SourceLocation(source_id=source_id, url_or_path=href),
                document_type="court_form",
                title=title,
                citation=form_id,
                form_id=form_id,
                retrieved_freshness_status="unknown",
                stale_form_risk="unknown_until_version_extracted",
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_forms_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed Maine Judicial Branch forms index links",
        extracted_count=len(forms),
    )
    return forms, event


def parse_form_text(text: str, *, source_id: str, url: str) -> tuple[CourtForm, ParserAuditEvent]:
    clean = normalize_whitespace(text)
    id_match = _FORM_ID_RE.search(clean)
    version_match = _VERSION_RE.search(clean)
    form_id = normalize_form_id(id_match.group(0)) if id_match else None
    title = clean[:120] if clean else "Maine court form"
    form = CourtForm(
        document_id=stable_source_id("me-court-form", url),
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="court_form",
        title=title,
        text=clean,
        citation=form_id,
        form_id=form_id,
        version_date=version_match.group(1) if version_match else None,
        retrieved_freshness_status="known_version_date" if version_match else "unknown",
        stale_form_risk="needs_forms_freshness_gold_check",
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_form_text",
        parser_version=PARSER_VERSION,
        status="parsed" if form_id else "partial",
        message="parsed court form text metadata",
        extracted_count=1 if form_id else 0,
        warnings=[] if version_match else ["form version date not found"],
    )
    return form, event
