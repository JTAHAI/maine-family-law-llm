from __future__ import annotations

import re
from urllib.parse import urlparse

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import OpinionReference

PARSER_VERSION = "maine_law_court_opinion_index_parser_v1"
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)
_DOCKET_RE = re.compile(r"(?:Me\.|ME)?\s*(?:Law Court)?\s*(?:No\.)?\s*([A-Z]{3}-\d{2,}(?:-\d+)?|\d{4}\s+ME\s+\d+)", re.I)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\b")


def _opinion_id_from_href(href: str) -> str:
    path = urlparse(href).path
    return stable_source_id("me-lawcourt-opinion", path)


def parse_law_court_opinion_index(
    html: str, *, source_id: str, url: str
) -> tuple[list[OpinionReference], ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    opinions: list[OpinionReference] = []
    for link in links:
        href = link["href"]
        text = normalize_whitespace(link["text"])
        if not _PDF_RE.search(href):
            continue
        docket_match = _DOCKET_RE.search(text)
        date_match = _DATE_RE.search(text)
        opinions.append(
            OpinionReference(
                opinion_id=_opinion_id_from_href(href),
                title=text or href.rsplit("/", 1)[-1],
                href=href,
                decision_date=date_match.group(1) if date_match else None,
                docket_number=docket_match.group(1) if docket_match else None,
                source_id=source_id,
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_law_court_opinion_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed Maine Law Court published-opinion index",
        extracted_count=len(opinions),
        metadata={"text_length": len(visible_text)},
    )
    return opinions, event
