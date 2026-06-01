from __future__ import annotations

import re

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import CourtRule, SourceLocation

PARSER_VERSION = "maine_rules_parser_v2"
_RULE_RE = re.compile(r"\b(?:Rule|RULE|M\.R\.\s*Civ\.\s*P\.)\s*(\d+(?:\.\d+)?[A-Z]?)\b", re.I)


def _infer_rule_set(text: str, url: str) -> str:
    combined = f"{url}\n{text[:4000]}".lower()
    if "appellate" in combined or "mr_app" in combined:
        return "Maine Rules of Appellate Procedure"
    if "evidence" in combined or "mr_evid" in combined:
        return "Maine Rules of Evidence"
    if "probate" in combined or "mr_prob" in combined:
        return "Maine Rules of Probate Procedure"
    if "electronic court systems" in combined or "mrecs" in combined:
        return "Maine Rules of Electronic Court Systems"
    if "standing order" in combined or "rule 120" in combined:
        return "Maine Rules of Civil Procedure / Family Division standing order"
    return "Maine Court Rules"


def parse_rules_text(text: str, *, source_id: str, url: str) -> tuple[list[CourtRule], ParserAuditEvent]:
    visible_text = normalize_whitespace(text)
    rule_set = _infer_rule_set(text, url)
    seen: set[str] = set()
    rules: list[CourtRule] = []
    for match in _RULE_RE.finditer(text):
        rule_number = match.group(1)
        if rule_number in seen:
            continue
        seen.add(rule_number)
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 160)
        title = normalize_whitespace(text[start:end]) or f"Rule {rule_number}"
        document_id = stable_source_id("me-court-rule", f"{url}#rule-{rule_number}")
        citation_prefix = "M.R. Civ. P." if "Civil Procedure" in rule_set or "standing order" in rule_set.lower() else "Maine Rule"
        rules.append(
            CourtRule(
                document_id=document_id,
                source_location=SourceLocation(source_id=source_id, url_or_path=f"{url}#rule-{rule_number}"),
                document_type="court_rule",
                title=title[:240],
                citation=f"{citation_prefix} {rule_number}",
                retrieved_freshness_status="retrieved_timestamp_known",
                rule_set=rule_set,
                rule_number=rule_number,
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_rules_pdf",
        parser_version=PARSER_VERSION,
        status="parsed" if rules else "parsed_empty",
        message="parsed Maine court rules text extracted from official snapshot",
        extracted_count=len(rules),
        metadata={"text_length": len(visible_text), "rule_set": rule_set},
    )
    return rules, event


def parse_rules_index(html: str, *, source_id: str, url: str) -> tuple[list[CourtRule], ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    rules: list[CourtRule] = []
    for link in links:
        label = normalize_whitespace(link["text"])
        href = link["href"]
        if "rule" not in label.lower() and "rule" not in href.lower():
            continue
        match = _RULE_RE.search(label)
        document_id = stable_source_id("me-court-rule", href)
        rules.append(
            CourtRule(
                document_id=document_id,
                source_location=SourceLocation(source_id=source_id, url_or_path=href),
                document_type="court_rule",
                title=label or href.rsplit("/", 1)[-1],
                citation=f"M.R. Civ. P. {match.group(1)}" if match else None,
                retrieved_freshness_status="unknown",
                rule_set="Maine Rules of Civil Procedure",
                rule_number=match.group(1) if match else None,
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="maine_rules_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed Maine Judicial Branch rules index",
        extracted_count=len(rules),
        metadata={"text_length": len(visible_text)},
    )
    return rules, event
