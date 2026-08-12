from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CitationKind = Literal["maine_statute", "maine_case", "maine_rule", "maine_form", "federal_statute"]


@dataclass(frozen=True)
class ParsedCitation:
    raw: str
    kind: CitationKind
    normalized: str
    start: int
    end: int
    title: str | None = None
    section: str | None = None
    reporter_year: str | None = None
    reporter_number: str | None = None
    rule_set: str | None = None
    rule_number: str | None = None
    form_id: str | None = None
    pinpoint: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "raw": self.raw,
            "kind": self.kind,
            "normalized": self.normalized,
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "section": self.section,
            "reporter_year": self.reporter_year,
            "reporter_number": self.reporter_number,
            "rule_set": self.rule_set,
            "rule_number": self.rule_number,
            "form_id": self.form_id,
            "pinpoint": self.pinpoint,
            "status": "unverified",
        }


# Maine citations appear in several common human and OCR variants.  Every pattern
# normalizes to one canonical key before lookup; the original text remains intact.
_SECTION = r"\d+[A-Z]?(?:-[A-Z0-9]+)?(?:\([A-Z0-9]+\))*"
_TITLE = r"\d+(?:-[A-Z])?"
_MRS = r"(?:M\.?\s*R\.?\s*S\.?(?:\s*A\.?)?|MRSA?|MRS)"

MAINE_STATUTE_PATTERN = re.compile(
    rf"\b(?P<title>{_TITLE})\s*{_MRS}\s*§+\s*(?P<section>{_SECTION})(?![A-Z0-9])",
    re.I,
)
MAINE_TITLE_SECTION_PATTERN = re.compile(
    rf"\bTITLE\s+(?P<title>{_TITLE})\s*,?\s*(?:M\.?R\.?S\.?(?:A\.?)?\s*)?§+\s*(?P<section>{_SECTION})(?![A-Z0-9])",
    re.I,
)
MAINE_CASE_PATTERN = re.compile(
    r"\b(?P<year>20\d{2}|19\d{2})\s+ME\s+(?P<number>\d+)"
    r"(?P<pinpoint>\s*,\s*(?:¶+|para\.?|paragraph)\s*\d+(?:-\d+)?)?\b",
    re.I,
)
MAINE_RULE_PATTERN = re.compile(
    r"\b(?P<rule_set>M\.?\s*R\.?\s*(?:Civ|App|Evid)\.?\s*P\.?)\s*(?:Rule\s*)?(?P<rule>\d+[A-Z]?(?:\([A-Z0-9]+\))*)\b",
    re.I,
)
MAINE_FORM_PATTERN = re.compile(r"\b(?P<prefix>FM|PA|CV|PB)[-\s]?\s*(?P<number>\d{3}[A-Z]?)\b", re.I)
FEDERAL_STATUTE_PATTERN = re.compile(
    rf"\b(?P<title>\d+)\s*U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<section>{_SECTION})(?![A-Z0-9])",
    re.I,
)


def normalize_maine_statute(title: str, section: str) -> str:
    return f"{title.upper()} M.R.S. § {section.upper()}"


def normalize_maine_case(year: str, number: str) -> str:
    return f"{year} ME {int(number)}"


def normalize_rule(rule_set: str, rule_number: str) -> str:
    compact = re.sub(r"[^A-Z]", "", rule_set.upper())
    if "APP" in compact:
        display = "M.R. App. P."
    elif "EVID" in compact:
        display = "M.R. Evid. P."
    else:
        display = "M.R. Civ. P."
    return f"{display} {rule_number.upper()}"


def normalize_form(prefix: str, number: str) -> str:
    return f"{prefix.upper()}-{number.upper()}"


def normalize_federal_statute(title: str, section: str) -> str:
    return f"{title} U.S.C. § {section.upper()}"


def citation_aliases(citation: ParsedCitation) -> tuple[str, ...]:
    """Return deterministic display/search aliases for an already parsed citation."""
    aliases = {citation.normalized}
    if citation.kind == "maine_statute" and citation.title and citation.section:
        aliases.update(
            {
                f"{citation.title} M.R.S.A. § {citation.section}",
                f"{citation.title} MRSA § {citation.section}",
                f"{citation.title} MRS § {citation.section}",
                f"Title {citation.title} § {citation.section}",
            }
        )
    elif citation.kind == "maine_form" and citation.form_id:
        aliases.add(citation.form_id.replace("-", " "))
    return tuple(sorted(aliases))


def _append_statute_match(citations: list[ParsedCitation], match: re.Match[str]) -> None:
    title = match.group("title").upper()
    section = match.group("section").upper()
    citations.append(
        ParsedCitation(
            raw=match.group(0),
            kind="maine_statute",
            normalized=normalize_maine_statute(title, section),
            start=match.start(),
            end=match.end(),
            title=title,
            section=section,
        )
    )


def extract_citations(text: str) -> list[ParsedCitation]:
    citations: list[ParsedCitation] = []
    occupied: list[tuple[int, int]] = []

    for pattern in (MAINE_STATUTE_PATTERN, MAINE_TITLE_SECTION_PATTERN):
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(span[0] < end and start < span[1] for start, end in occupied):
                continue
            _append_statute_match(citations, match)
            occupied.append(span)

    for match in MAINE_CASE_PATTERN.finditer(text):
        pinpoint = match.group("pinpoint")
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="maine_case",
                normalized=normalize_maine_case(match.group("year"), match.group("number")),
                start=match.start(),
                end=match.end(),
                reporter_year=match.group("year"),
                reporter_number=str(int(match.group("number"))),
                pinpoint=pinpoint.strip(" ,") if pinpoint else None,
            )
        )
    for match in MAINE_RULE_PATTERN.finditer(text):
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="maine_rule",
                normalized=normalize_rule(match.group("rule_set"), match.group("rule")),
                start=match.start(),
                end=match.end(),
                rule_set=match.group("rule_set"),
                rule_number=match.group("rule").upper(),
            )
        )
    for match in MAINE_FORM_PATTERN.finditer(text):
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="maine_form",
                normalized=normalize_form(match.group("prefix"), match.group("number")),
                start=match.start(),
                end=match.end(),
                form_id=normalize_form(match.group("prefix"), match.group("number")),
            )
        )
    for match in FEDERAL_STATUTE_PATTERN.finditer(text):
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="federal_statute",
                normalized=normalize_federal_statute(match.group("title"), match.group("section")),
                start=match.start(),
                end=match.end(),
                title=match.group("title"),
                section=match.group("section").upper(),
            )
        )
    return sorted(citations, key=lambda citation: (citation.start, citation.end, citation.kind))


def extract_maine_statute_citations(text: str):
    return [citation.to_dict() for citation in extract_citations(text) if citation.kind == "maine_statute"]
