from __future__ import annotations

import re

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import SourceLocation, StatuteSection, StatuteTitle

PARSER_VERSION = "maine_revisor_parser_v1"
_DATA_EXTRACTED_RE = re.compile(r"Data for this page extracted on\s+([^\.]+)\.", re.I)
_SECTION_LINK_RE = re.compile(r"title(?P<title>\d+[a-z-]*)sec(?P<section>[\w.-]+)\.html", re.I)
_CHAPTER_RE = re.compile(r"Chapter\s+(?P<chapter>\d+[A-Z]?)\s*:\s*(?P<heading>.*?)\s*§(?P<range>[\w\s.,&-]+)", re.I)
_SECTION_HEADING_RE = re.compile(r"§\s*(?P<section>[\w.-]+)\.\s*(?P<heading>[^\n]+)")
_TITLE_RE = re.compile(r"Title\s+(?P<title>\d+[A-Z-]*)", re.I)


def infer_revisor_freshness(html: str) -> tuple[str, str | None]:
    match = _DATA_EXTRACTED_RE.search(normalize_whitespace(html))
    if not match:
        return "unknown", None
    extracted = match.group(1).strip()
    # Do not classify as current/stale here. The date must be compared by the freshness
    # updater once a local policy is configured.
    return "known_extracted_timestamp", extracted


def parse_revisor_title_index(html: str, *, source_id: str, url: str) -> tuple[StatuteTitle, ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    title_match = _TITLE_RE.search(visible_text)
    title_number = title_match.group("title").upper() if title_match else "unknown"
    freshness_status, extracted_at = infer_revisor_freshness(html)

    section_links: list[dict[str, str]] = []
    for link in links:
        match = _SECTION_LINK_RE.search(link["href"])
        if match:
            section_links.append(
                {
                    "title": match.group("title").upper(),
                    "section": match.group("section"),
                    "text": link["text"],
                    "href": link["href"],
                    "source_id": stable_source_id("me-statute-section", link["href"]),
                }
            )

    chapters = [match.groupdict() for match in _CHAPTER_RE.finditer(visible_text)]
    document = StatuteTitle(
        document_id=f"statute-title-{title_number.lower()}",
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="statute_title",
        title=f"Maine Revised Statutes Title {title_number}",
        text=visible_text,
        citation=f"Title {title_number}",
        retrieved_freshness_status=freshness_status,
        title_number=title_number,
        chapters=chapters,
        section_links=section_links,
        data_extracted_at=extracted_at,
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_revisor_title_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed Maine Revisor title index",
        extracted_count=len(section_links),
        metadata={"chapter_count": len(chapters), "data_extracted_at": extracted_at},
    )
    return document, event


def parse_revisor_section_html(html: str, *, source_id: str, url: str) -> tuple[StatuteSection, ParserAuditEvent]:
    _links, visible_text = collect_links_and_text(html, base_url=url)
    title_match = _TITLE_RE.search(visible_text)
    title_number = title_match.group("title").upper() if title_match else "unknown"
    section_match = _SECTION_HEADING_RE.search(visible_text)
    section_number = section_match.group("section") if section_match else "unknown"
    heading = normalize_whitespace(section_match.group("heading")) if section_match else "unknown"
    freshness_status, extracted_at = infer_revisor_freshness(html)
    subsections = re.findall(r"(?:^|\s)(\d+[A-Z]?\.)\s+([^\n§]{8,180})", visible_text)

    document = StatuteSection(
        document_id=f"statute-{title_number.lower()}-{section_number.lower()}",
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="statute_section",
        title=f"{title_number} M.R.S. § {section_number}: {heading}",
        text=visible_text,
        citation=f"{title_number} M.R.S. § {section_number}",
        retrieved_freshness_status=freshness_status,
        title_number=title_number,
        section_number=section_number,
        section_heading=heading,
        subsections=[normalize_whitespace(f"{num} {body}") for num, body in subsections],
        metadata={"data_extracted_at": extracted_at},
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_revisor_section",
        parser_version=PARSER_VERSION,
        status="parsed" if section_number != "unknown" else "partial",
        message="parsed Maine Revisor statute section",
        extracted_count=len(document.subsections),
        metadata={"section_number": section_number, "data_extracted_at": extracted_at},
    )
    return document, event


def parse_revisor_html(html: str, *, source_id: str, url: str):
    if "ch0sec0" in url or "Chapter" in html:
        return parse_revisor_title_index(html, source_id=source_id, url=url)
    return parse_revisor_section_html(html, source_id=source_id, url=url)
