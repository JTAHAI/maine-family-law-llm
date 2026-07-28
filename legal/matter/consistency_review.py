from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)
_DOCKET_RE = re.compile(r"\b(?:Docket|Case)\s*(?:No\.?|Number)?\s*[:#]?\s*([A-Z0-9-]{5,40})\b", re.I)
_MONEY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{2})?)")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
_CONTEXT_TERMS = {
    "hearing_date": ("hearing", "trial", "conference", "mediation"),
    "service_date": ("served", "service", "received summons"),
    "order_date": ("order dated", "judgment dated", "decree dated", "entered on"),
    "filing_date": ("filed", "filing", "submitted to court"),
    "deadline_date": ("deadline", "due", "no later than", "respond by"),
    "birth_date": ("date of birth", "dob", "born"),
    "support_amount": ("child support", "weekly support", "monthly support"),
    "arrears_amount": ("arrears", "past due", "unpaid support"),
    "income_amount": ("gross income", "net income", "annual income", "weekly income"),
}


@dataclass(frozen=True)
class SourceText:
    document_id: str
    filename: str
    text: str


@dataclass(frozen=True)
class HardFieldOccurrence:
    field_type: str
    context_key: str
    normalized_value: str
    displayed_value: str
    document_id: str
    filename: str
    start: int
    end: int
    context: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    field_type: str
    context_key: str
    severity: str
    values: tuple[str, ...]
    occurrences: tuple[HardFieldOccurrence, ...]
    legal_significance: str = "not_determined"
    review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "field_type": self.field_type,
            "context_key": self.context_key,
            "severity": self.severity,
            "values": list(self.values),
            "occurrences": [item.to_dict() for item in self.occurrences],
            "legal_significance": self.legal_significance,
            "review_required": self.review_required,
        }


def _context(text: str, start: int, end: int, radius: int = 100) -> str:
    return " ".join(text[max(0, start - radius) : min(len(text), end + radius)].split())


def _context_key(field_type: str, surrounding: str) -> str | None:
    lowered = surrounding.lower()
    compatible = (
        ("date", key) for key in _CONTEXT_TERMS if key.endswith("_date")
    ) if field_type == "date" else (
        ("money", key) for key in _CONTEXT_TERMS if key.endswith("_amount")
    )
    for _kind, key in compatible:
        if any(term in lowered for term in _CONTEXT_TERMS[key]):
            return key
    if field_type == "docket_number":
        return field_type
    # Contact details are extracted for source review, but multiple people commonly
    # have different email addresses or phone numbers. Without a stable subject
    # identifier, treating those differences as contradictions creates unsafe noise.
    if field_type in {"email", "phone"}:
        return None
    return None


def _normalize_date(value: str) -> str:
    raw = value.strip().replace("Sept.", "Sep.")
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%b. %d, %Y",
    ):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw.casefold()


def extract_hard_fields(source: SourceText) -> tuple[HardFieldOccurrence, ...]:
    text = source.text[:2_000_000]
    found: list[HardFieldOccurrence] = []
    patterns = (
        ("date", _DATE_RE),
        ("docket_number", _DOCKET_RE),
        ("money", _MONEY_RE),
        ("email", _EMAIL_RE),
        ("phone", _PHONE_RE),
    )
    for field_type, pattern in patterns:
        for match in pattern.finditer(text):
            displayed = match.group(1) if field_type in {"docket_number", "money"} else match.group(0)
            surrounding = _context(text, match.start(), match.end())
            key = _context_key(field_type, surrounding)
            if key is None:
                continue
            if field_type == "date":
                normalized = _normalize_date(displayed)
            elif field_type == "money":
                normalized = displayed.replace(",", "")
            elif field_type == "phone":
                normalized = re.sub(r"\D", "", displayed)[-10:]
            else:
                normalized = displayed.strip().casefold()
            found.append(
                HardFieldOccurrence(
                    field_type=field_type,
                    context_key=key,
                    normalized_value=normalized,
                    displayed_value=displayed.strip(),
                    document_id=source.document_id,
                    filename=source.filename,
                    start=match.start(),
                    end=match.end(),
                    context=surrounding,
                )
            )
    return tuple(found)


def find_cross_document_conflicts(sources: Iterable[SourceText]) -> tuple[ConflictRecord, ...]:
    grouped: dict[tuple[str, str], list[HardFieldOccurrence]] = {}
    for source in sources:
        for occurrence in extract_hard_fields(source):
            grouped.setdefault((occurrence.field_type, occurrence.context_key), []).append(occurrence)

    conflicts: list[ConflictRecord] = []
    for (field_type, key), occurrences in sorted(grouped.items()):
        documents = {item.document_id for item in occurrences}
        values = sorted({item.normalized_value for item in occurrences})
        if len(documents) < 2 or len(values) < 2:
            continue
        severity = "high" if key in {"hearing_date", "deadline_date", "docket_number"} else "medium"
        conflicts.append(
            ConflictRecord(
                conflict_id=f"conflict_{field_type}_{key}_{len(conflicts) + 1}",
                field_type=field_type,
                context_key=key,
                severity=severity,
                values=tuple(values),
                occurrences=tuple(
                    sorted(occurrences, key=lambda item: (item.filename.casefold(), item.start))
                ),
            )
        )
    return tuple(conflicts)
