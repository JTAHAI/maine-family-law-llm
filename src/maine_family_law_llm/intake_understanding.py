"""Deterministic, safety-first intake understanding for local family-law chats.

The parser converts plain-language intake into transparent routing signals. It
never decides that abuse, contempt, interference, jurisdiction, or any other
legal standard is established. The original document and verified source cards
remain controlling.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from .search_normalization import normalize_search_query

MAX_INTAKE_CHARS = 12_000

TYPO_NORMALIZATION = {
    "interferrence": "interference",
    "interferance": "interference",
    "parental alienation": "parent-child contact interference",
    "custody": "parental rights and responsibilities",
    "visitation": "parent-child contact",
    "restraining order": "protection from abuse order",
    "pfa": "protection from abuse",
    "post judgement": "post-judgment",
    "coparent": "co-parent",
    "co parent": "co-parent",
    "subpeona": "subpoena",
    "subpena": "subpoena",
}

IMMEDIATE_SAFETY_TERMS = (
    "immediate danger",
    "unsafe right now",
    "someone may be unsafe",
    "may be unsafe",
    "i feel unsafe",
    "i am unsafe",
    "i'm unsafe",
    "i am not safe",
    "i'm not safe",
    "do not feel safe",
    "don't feel safe",
    "cannot go home safely",
    "can't go home safely",
    "afraid to go home",
    "hurt me",
    "kill me",
    "threatened me",
    "threatened to hurt",
    "threatened to kill",
    "weapon",
    "emergency",
)

NEGATED_SAFETY_PHRASES_THAT_MEAN_UNSAFE = (
    "i am not safe",
    "i'm not safe",
    "do not feel safe",
    "don't feel safe",
)

CHILD_SAFETY_TERMS = (
    "child is unsafe",
    "child may be unsafe",
    "danger to my child",
    "danger to the child",
    "child abuse",
    "child was hurt",
    "child is being hurt",
    "neglect",
)

SOURCE_FOLLOWUP_TERMS = (
    "give me the source cards",
    "show source cards",
    "show me the source cards",
    "open source cards",
    "source cards please",
    "show sources",
    "show the sources",
    "where did you find that",
    "show the snippets",
    "open the matches",
    "show all matches",
    "show all three",
    "open the first one",
    "open the second one",
    "open the third one",
    "show maine law sources",
    "show the maine law sources",
    "show law sources",
    "show legal sources",
    "show my record sources",
    "show record sources",
    "show private record sources",
)

CONTINUATION_PATTERNS = (
    "what should i gather",
    "what do i gather",
    "what should i do next",
    "what do i do next",
    "what next",
    "then what",
    "what now",
    "what questions should i ask",
    "what should i ask",
    "can you explain that",
    "explain that",
    "what does that mean",
    "how do i prepare",
    "how should i prepare",
    "and what about",
    "what about that",
    "what about this",
    "and then",
)

TASK_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("corpus_inventory", (
        "list what is in my indexed corpus",
        "what is in my indexed corpus",
        "list indexed corpus",
        "show corpus inventory",
        "show indexed files",
        "list indexed files",
        "what files are indexed",
        "list indexed pdfs",
        "show indexed pdfs",
    )),
    ("record_search", ("search contents", "search records", "find all mentions", "find mentions", "look for", "search for", "find in my records", "where does it say", "find pdf", "find a pdf", "pdf re")),
    ("served_papers", ("i was served", "served with", "summons", "complaint was served", "got court papers", "received court papers")),
    ("hearing_preparation", ("hearing", "court tomorrow", "court date", "prepare for court", "what do i bring to court", "case management conference", "mediation date")),
    ("understand_order", ("understand the order", "understand my order", "help me understand my order", "what does this order mean", "what does my order mean", "what does the order mean", "order says", "confusing order", "unclear order", "interpret the order", "reasonable contact")),
    ("enforce_order", ("not following the order", "violating the order", "enforce", "contempt", "denied contact", "blocked contact", "interference", "obstruction")),
    ("modify_order", ("modify", "change the order", "change parenting", "change contact", "changed circumstances")),
    ("child_support", ("child support", "support payment", "arrears", "past due support", "income affidavit")),
    ("organize_records", ("organize records", "organize evidence", "build a timeline", "sort documents", "what should i gather")),
    ("find_printable", ("printable", "worksheet", "checklist", "planner", "something to print")),
    ("plain_language_explanation", ("what does", "explain", "in plain language", "help me understand", "what is")),
)

ISSUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "divorce": ("divorce", "separation", "marriage"),
    "parental_rights_responsibilities": ("parental rights", "parenting", "primary residence", "custody"),
    "contact_schedule": ("contact", "visitation", "parenting time", "exchange", "holiday schedule", "denied contact"),
    "parent_child_contact_interference": ("interference", "obstruction", "blocked contact", "denied contact", "withholding contact", "disparagement", "contact refusal"),
    "child_support": ("child support", "arrears", "support payment", "income affidavit"),
    "parentage": ("parentage", "paternity", "unmarried parents", "never married"),
    "post_judgment": ("post-judgment", "modify", "enforce", "contempt", "existing order"),
    "protection_from_abuse": ("protection from abuse", "domestic violence", "abuse", "restraining order"),
    "school_health_coordination": ("school", "teacher", "doctor", "medical", "therapy", "counselor", "childcare"),
    "records_evidence": ("records", "evidence", "messages", "emails", "documents", "timeline", "exhibits"),
    "appeal": ("appeal", "law court", "transcript", "preservation", "remand"),
    "jurisdiction": ("jurisdiction", "another state", "out of state", "uccjea", "relocate", "moving"),
}

POSTURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("appeal", ("appeal", "law court", "notice of appeal")),
    ("post_judgment", ("post-judgment", "modify", "enforce", "contempt", "existing final order")),
    ("temporary_order", ("temporary order", "interim order")),
    ("final_order", ("final order", "judgment")),
    ("initial_complaint", ("i was served", "summons", "complaint", "starting a case", "received court papers", "got court papers")),
    ("hearing_pending", ("hearing", "conference", "mediation")),
)

DOCUMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "order": ("order", "judgment", "decree"),
    "summons_or_complaint": ("summons", "complaint", "petition"),
    "hearing_notice": ("hearing notice", "notice of hearing", "court date"),
    "motion": ("motion", "request to modify", "motion to enforce", "contempt motion"),
    "messages": ("text messages", "messages", "emails", "communication app"),
    "school_records": ("school records", "attendance", "report card", "teacher"),
    "medical_or_therapy_records": ("medical records", "therapy records", "doctor", "counselor"),
    "financial_records": ("pay stubs", "tax return", "income", "bank statements", "childcare costs"),
}

REQUESTED_ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("understand_or_clarify_order", ("clarify", "what does my order mean", "what does this order mean", "interpret the order")),
    ("prepare_for_hearing", ("prepare for court", "prepare for hearing", "what do i bring to court")),
    ("enforce_existing_order", ("enforce", "not following the order", "violating the order")),
    ("seek_contempt_review", ("contempt", "motion for contempt")),
    ("modify_existing_order", ("modify", "change the order", "changed circumstances")),
    ("change_parent_child_contact", ("change contact", "parenting time", "visitation", "supervised contact")),
    ("change_primary_residence", ("primary residence", "sole residence")),
    ("address_child_support", ("child support", "arrears", "support payment")),
    ("seek_safety_relief", ("protection from abuse", "protection order", "restraining order")),
    ("appeal_or_preserve_record", ("appeal", "notice of appeal", "preserve the record")),
    ("organize_evidence", ("organize evidence", "build a timeline", "sort documents")),
)

DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-](?:\d{2}|\d{4}))?|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)\b",
    re.IGNORECASE,
)
DOCKET_PATTERN = re.compile(r"\b(?:docket|case)\s*(?:no\.?|number|#)?\s*[:#-]?\s*([A-Z0-9-]{5,})\b", re.IGNORECASE)
COURT_PATTERN = re.compile(r"\b([A-Z][A-Za-z ]{2,35}(?:District|Superior|Probate) Court)\b")
ORDINAL_SOURCE_PATTERN = re.compile(
    r"\b(?:open|show|display)\s+(?:me\s+)?(?:the\s+)?"
    r"(last|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"\d{1,2}(?:st|nd|rd|th)?)\s+"
    r"(?:(?:maine\s+law|law|legal|my\s+record|record|private\s+record|matter\s+record)\s+)?"
    r"(?:one|source|card|match)?\b",
    re.IGNORECASE,
)

NEGATION_WINDOW = re.compile(
    r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdid\s+not\b|\bdidn't\b|"
    r"\bwas\s+not\b|\bwasn't\b|\bis\s+not\b|\bisn't\b|\bhave\s+not\b|\bhaven't\b)"
    r"(?:\s+\w+){0,3}\s*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class IntakeSummary:
    normalized_text: str
    task: str = "general_question"
    issues: list[str] = field(default_factory=list)
    procedural_posture: str = "unknown"
    urgency_flags: list[str] = field(default_factory=list)
    dates_mentioned: list[str] = field(default_factory=list)
    critical_dates: list[dict[str, Any]] = field(default_factory=list)
    documents_mentioned: list[str] = field(default_factory=list)
    requested_actions: list[str] = field(default_factory=list)
    search_target: str = ""
    record_type_filter: str = ""
    source_card_selection: int = 0
    source_card_lane: str = "all"
    docket_number: str = ""
    court: str = ""
    child_relevant: bool = False
    user_goal: str = ""
    essential_follow_up_questions: list[str] = field(default_factory=list)
    routing_reasons: list[str] = field(default_factory=list)
    attention_level: str = "routine"
    confidence: float = 0.0
    interpretation_note: str = ""
    input_truncated: bool = False
    original_length: int = 0
    continuation_requested: bool = False
    context_inherited: bool = False
    continuity_reason: str = ""
    inherited_task: str = ""
    inherited_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IntakeSummary":
        """Restore a validated summary while ignoring unknown future fields."""

        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in dict(payload or {}).items() if key in allowed}
        values.setdefault("normalized_text", "")
        return cls(**values)


def _clean_user_text(value: str) -> tuple[str, bool, int]:
    raw = unicodedata.normalize("NFKC", str(value or ""))
    original_length = len(raw)
    raw = "".join(ch if ch in "\n\t" or ord(ch) >= 32 else " " for ch in raw)
    truncated = len(raw) > MAX_INTAKE_CHARS
    raw = raw[:MAX_INTAKE_CHARS]
    return " ".join(raw.strip().split()), truncated, original_length


def normalize_intake_text(value: str) -> str:
    text, _, _ = _clean_user_text(value)
    lowered = text.casefold()
    # Normalize common Word/PDF/OCR dash variants for routing while preserving
    # punctuation needed by the ordinary question-form fallback.
    lowered = lowered.translate(str.maketrans({
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2043": "-", "\u2212": "-",
        "\ufe58": "-", "\ufe63": "-", "\uff0d": "-", "\u00ad": "",
    }))
    for wrong, replacement in TYPO_NORMALIZATION.items():
        lowered = lowered.replace(wrong, replacement)
    return lowered


def _term_matches(text: str, term: str) -> Iterable[re.Match[str]]:
    escaped = re.escape(term.casefold())
    return re.finditer(rf"(?<!\w){escaped}(?!\w)", text.casefold())


def _affirmed_term(text: str, term: str) -> bool:
    for match in _term_matches(text, term):
        prefix = text[max(0, match.start() - 48):match.start()]
        if not NEGATION_WINDOW.search(prefix):
            return True
    return False


def _contains_any(text: str, terms: tuple[str, ...], *, negation_aware: bool = False) -> bool:
    matcher = _affirmed_term if negation_aware else lambda value, term: any(_term_matches(value, term))
    return any(matcher(text, term) for term in terms)


def _immediate_safety_present(text: str) -> bool:
    if _contains_any(text, NEGATED_SAFETY_PHRASES_THAT_MEAN_UNSAFE):
        return True
    ordinary_terms = tuple(
        term for term in IMMEDIATE_SAFETY_TERMS if term not in NEGATED_SAFETY_PHRASES_THAT_MEAN_UNSAFE
    )
    return _contains_any(text, ordinary_terms, negation_aware=True)


def _source_followup(text: str) -> bool:
    compact = text.strip(" .?!:")
    if compact in SOURCE_FOLLOWUP_TERMS:
        return True
    if ORDINAL_SOURCE_PATTERN.search(compact):
        return True
    if re.fullmatch(
        r"(?:please\s+)?(?:show|open|list|display)\s+(?:only\s+)?(?:the\s+)?"
        r"(?:maine\s+law|law|legal|my\s+records?|record|private\s+record)\s+"
        r"(?:sources?|source\s+cards?|cards?|matches?)",
        compact,
    ):
        return True
    return bool(re.fullmatch(r"(?:please\s+)?(?:show|open|give me)\s+(?:the\s+)?(?:prior|previous|last)\s+(?:sources|source cards|matches)", compact))


def _source_selection(text: str) -> int:
    match = ORDINAL_SOURCE_PATTERN.search(text)
    if not match:
        return 0
    value = match.group(1).casefold()
    words = {
        "last": -1,
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    if value in words:
        return words[value]
    number = re.match(r"\d{1,2}", value)
    if not number:
        return 0
    selected = int(number.group(0))
    return selected if 1 <= selected <= 24 else 0


def _source_lane(text: str) -> str:
    compact = text.casefold()
    if re.search(r"\b(?:my\s+records?|record|private\s+record|matter\s+record)\s+(?:sources?|cards?|matches?)\b", compact):
        return "private_record"
    if re.search(r"\b(?:maine\s+law|law|legal|authority)\s+(?:sources?|cards?|matches?)\b", compact):
        return "legal_authority"
    return "all"


def _continuation_requested(text: str) -> bool:
    compact = text.strip(" .?!:")
    if not compact or len(compact) > 240 or _source_followup(compact):
        return False
    if compact in CONTINUATION_PATTERNS:
        return True
    return any(compact.startswith(pattern + " ") for pattern in CONTINUATION_PATTERNS)


def _direct_record_search_command(text: str) -> bool:
    """Recognize list/show commands whose object is the selected matter records."""

    compact = normalize_search_query(text).canonical
    if not compact:
        return False
    explicit_record_object = re.fullmatch(
        r"(?:please )?(?:show|give|display|list|pull|find)(?: me)? "
        r"(?:a list of )?(?:all |every |everything )?.+ "
        r"(?:records?|documents?|files?|pdfs?)",
        compact,
    )
    broad_list_command = re.fullmatch(
        r"(?:please )?(?:show|give|display|list|pull)(?: me)? "
        r"(?:a list of )?(?:all|every|everything) .+",
        compact,
    )
    return bool(explicit_record_object or broad_list_command)


def _task(text: str) -> tuple[str, float, list[str]]:
    # Safety must outrank every routine routing signal, including service papers.
    if _immediate_safety_present(text):
        return "immediate_safety", 0.99, ["explicit immediate-safety language"]
    if _contains_any(text, CHILD_SAFETY_TERMS, negation_aware=True):
        return "child_safety", 0.97, ["explicit child-safety language"]
    if _source_followup(text):
        return "source_card_followup", 0.98, ["explicit request to reopen prior source cards"]
    # A command such as “show me a list of everything contempt-related” is a
    # record-search request, not a request to decide whether contempt exists.
    if _direct_record_search_command(text):
        return "record_search", 0.95, ["explicit command to list or show matching matter records"]
    for task, terms in TASK_PATTERNS:
        if _contains_any(text, terms, negation_aware=True):
            return task, 0.92, [f"matched {task.replace('_', ' ')} language"]
    if text.endswith("?") or text.startswith(("how ", "why ", "can ", "should ", "does ", "is ", "are ")):
        return "general_question", 0.64, ["question-form intake without a more specific task signal"]
    return "describe_situation", 0.56, ["narrative intake without a more specific task signal"]


def _search_target(original: str, normalized: str, task: str) -> str:
    if task != "record_search":
        return ""
    quoted = re.search(r'["“](.+?)["”]', original)
    if quoted:
        return normalize_search_query(quoted.group(1)).canonical[:240]
    target = normalize_search_query(normalized).canonical
    patterns = (
        r"^(?:please\s+)?find\s+all\s+mentions\s+of\s+",
        r"^(?:please\s+)?find\s+mentions\s+of\s+",
        r"^(?:please\s+)?search\s+(?:the\s+)?(?:contents|records)\s+(?:for\s+)?",
        r"^(?:please\s+)?search\s+for\s+",
        r"^(?:please\s+)?find\s+(?:a\s+)?pdfs?\s+(?:(?:re|about|on|for)\s*:?\s*)?",
        r"^(?:please\s+)?find\s+(?:in\s+my\s+records\s+)?",
        r"^(?:please\s+)?look\s+for\s+",
        r"^where\s+does\s+it\s+say\s+",
        r"^(?:please\s+)?(?:show|give|display|list|pull)\s+(?:me\s+)?"
        r"(?:a\s+)?(?:list\s+of\s+)?(?:all|every|everything)\s+",
        r"^(?:please\s+)?(?:show|give|display|list|pull|find)\s+(?:me\s+)?"
        r"(?:a\s+)?(?:list\s+of\s+)?",
    )
    for pattern in patterns:
        target = re.sub(pattern, "", target).strip(" .?!:")
    target = re.sub(r"\s+(?:records?|documents?|files?|pdfs?)$", "", target).strip()
    # “contempt-related” describes the requested set; “related” itself is not
    # a meaningful content token and must not suppress exact contempt matches.
    target = re.sub(r"\s+related$", "", target).strip()
    return target[:240]


def _parse_absolute_date(raw: str, reference: date) -> tuple[str, str, float]:
    cleaned = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned.replace(",", ""))
    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%m-%d-%y",
        "%B %d %Y",
        "%b %d %Y",
    ):
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            return parsed.isoformat(), "explicit_date", 0.9
        except ValueError:
            continue
    for fmt in ("%m/%d", "%m-%d", "%B %d", "%b %d"):
        try:
            partial = datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
        candidate = partial.replace(year=reference.year)
        if candidate < reference - timedelta(days=30):
            candidate = candidate.replace(year=reference.year + 1)
        return candidate.isoformat(), "year_inferred_from_reference_date", 0.68
    return "", "unparsed_date_text", 0.45


def _date_kind(text: str, start: int, end: int) -> str:
    """Classify a date by the nearest nearby event phrase, not a wide bag of words."""

    lowered = text.casefold()
    groups = {
        "service_date": ("served", "service", "received court papers", "got court papers", "court papers on"),
        "hearing_date": (
            "hearing",
            "court date",
            "court is",
            "court on",
            "court tomorrow",
            "court today",
            "appear in court",
            "appearance",
            "conference",
            "mediation",
            "trial",
        ),
        "response_or_filing_deadline": ("deadline", "due", "respond", "response", "answer by", "file by", "must file"),
    }
    center = (start + end) / 2
    candidates: list[tuple[float, str]] = []
    window_start = max(0, start - 90)
    window_end = min(len(lowered), end + 90)
    for kind, terms in groups.items():
        for term in terms:
            for match in _term_matches(lowered[window_start:window_end], term):
                absolute_center = window_start + (match.start() + match.end()) / 2
                candidates.append((abs(absolute_center - center), kind))
    return min(candidates, default=(9999.0, "mentioned_date"))[1]


def _extract_critical_dates(original: str, reference: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for match in DATE_PATTERN.finditer(original):
        raw = match.group(0)
        normalized_date, normalization_basis, confidence = _parse_absolute_date(raw, reference)
        events.append({
            "kind": _date_kind(original, match.start(), match.end()),
            "raw": raw,
            "normalized_date": normalized_date,
            "normalization_basis": normalization_basis,
            "confidence": confidence,
        })
    relative_map = {
        "yesterday": reference - timedelta(days=1),
        "today": reference,
        "tonight": reference,
        "tomorrow": reference + timedelta(days=1),
        "next week": reference + timedelta(days=7),
    }
    lowered = original.casefold()
    for raw, normalized in relative_map.items():
        for match in _term_matches(lowered, raw):
            events.append({
                "kind": _date_kind(lowered, match.start(), match.end()),
                "raw": raw,
                "normalized_date": normalized.isoformat(),
                "normalization_basis": "relative_to_local_reference_date",
                "confidence": 0.72 if raw == "next week" else 0.86,
            })
    for match in re.finditer(r"\bin\s+(\d{1,2})\s+(day|days|week|weeks)\b", lowered):
        count = int(match.group(1))
        unit = match.group(2)
        days = count * (7 if unit.startswith("week") else 1)
        events.append(
            {
                "kind": _date_kind(lowered, match.start(), match.end()),
                "raw": match.group(0),
                "normalized_date": (reference + timedelta(days=days)).isoformat(),
                "normalization_basis": "relative_to_local_reference_date",
                "confidence": 0.76,
            }
        )
    if _contains_any(lowered, ("this week",)):
        start = lowered.find("this week")
        events.append({"kind": _date_kind(lowered, start, start + len("this week")), "raw": "this week", "normalized_date": "", "normalization_basis": "range_not_normalized", "confidence": 0.62})
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        key = (str(event["kind"]), str(event["raw"]).casefold(), str(event["normalized_date"]))
        if key in seen:
            continue
        seen.add(key)
        normalized = str(event.get("normalized_date") or "")
        review_flags: list[str] = []
        days_from_reference: int | None = None
        if normalized:
            try:
                days_from_reference = (date.fromisoformat(normalized) - reference).days
            except ValueError:
                review_flags.append("normalized_date_unparseable")
        if event.get("normalization_basis") == "year_inferred_from_reference_date":
            review_flags.append("year_inferred_confirm_against_official_paper")
        elif event.get("normalization_basis") == "relative_to_local_reference_date":
            review_flags.append("relative_date_calculated_locally")
        elif event.get("normalization_basis") in {"range_not_normalized", "unparsed_date_text"}:
            review_flags.append("date_range_or_text_requires_manual_review")
        if event.get("kind") in {"hearing_date", "response_or_filing_deadline"} and days_from_reference is not None:
            if days_from_reference < 0:
                review_flags.append("listed_event_date_appears_past")
            elif days_from_reference == 0:
                review_flags.append("listed_event_date_is_today")
            elif days_from_reference <= 3:
                review_flags.append("listed_event_date_within_three_days")
            elif days_from_reference <= 14:
                review_flags.append("listed_event_date_within_fourteen_days")
        event["days_from_reference"] = days_from_reference
        event["review_flags"] = review_flags
        deduped.append(event)
    return deduped[:12]


def _requested_actions(text: str) -> list[str]:
    return [label for label, terms in REQUESTED_ACTION_PATTERNS if _contains_any(text, terms, negation_aware=True)]


def _attention_level(task: str, urgency: list[str], critical_dates: list[dict[str, Any]], reference: date) -> str:
    if "immediate_safety" in urgency or "urgent_child_safety" in urgency:
        return "emergency_or_urgent_safety"
    for event in critical_dates:
        normalized = str(event.get("normalized_date") or "")
        if event.get("kind") in {"hearing_date", "response_or_filing_deadline"} and normalized:
            try:
                days = (date.fromisoformat(normalized) - reference).days
            except ValueError:
                continue
            if days <= 3:
                return "urgent_deadline"
            if days <= 14:
                return "prompt_deadline_review"
    if "served_papers" in urgency or "possible_deadline" in urgency or task == "hearing_preparation":
        return "prompt_review"
    return "routine"


def _follow_ups(summary: IntakeSummary) -> list[str]:
    questions: list[str] = []
    kinds = {str(item.get("kind") or "") for item in summary.critical_dates}
    if summary.task == "served_papers":
        if "service_date" not in kinds:
            questions.append("What date were you served?")
        if not ({"hearing_date", "response_or_filing_deadline"} & kinds):
            questions.append("What hearing, response, or filing date appears on the papers?")
        if not summary.issues:
            questions.append("What type of case do the papers identify: divorce, parental rights, parentage, support, or protection from abuse?")
    elif summary.task in {"enforce_order", "modify_order", "understand_order"}:
        if "order" not in summary.documents_mentioned:
            questions.append("Do you have the complete signed order, including later orders that may change it?")
        questions.append("What exact paragraph is involved, and what outcome are you trying to understand or request?")
        if summary.task == "enforce_order":
            questions.append("What happened, on what dates, and what record supports each event?")
    elif summary.task == "record_search":
        if not summary.search_target:
            questions.append("What exact word or phrase should I search for in the selected records?")
    elif summary.task == "corpus_inventory":
        questions.append("Should I narrow the inventory to PDFs, messages, attachments, or another record type?")
    elif summary.task == "hearing_preparation":
        if "hearing_date" not in kinds:
            questions.append("What is the hearing date and what type of hearing is listed on the notice?")
        questions.append("What order, motion, or issue will the court be addressing?")
    elif summary.task == "child_support":
        questions.append("Is this initial support, a requested change, enforcement, arrears, or understanding an existing order?")
    elif summary.task == "describe_situation":
        questions.append("What outcome are you trying to understand or prepare for?")
    if summary.attention_level in {"prompt_review", "prompt_deadline_review", "urgent_deadline"} and not summary.critical_dates:
        questions.append("Is there a hearing, service date, or filing deadline shown on an official paper?")
    return list(dict.fromkeys(questions))[:3]


def parse_intake(
    question: str,
    matter_context: str = "",
    *,
    reference_date: date | None = None,
    prior_intake: dict[str, Any] | IntakeSummary | None = None,
) -> IntakeSummary:
    original, truncated, original_length = _clean_user_text(question)
    normalized = normalize_intake_text(original)
    context = normalize_intake_text(matter_context)
    combined = f"{normalized} {context}".strip()
    reference = reference_date or date.today()

    task, confidence, reasons = _task(normalized)
    issues = [label for label, terms in ISSUE_PATTERNS.items() if _contains_any(combined, terms, negation_aware=True)]

    posture = "unknown"
    for label, terms in POSTURE_PATTERNS:
        if _contains_any(combined, terms, negation_aware=True):
            posture = label
            reasons.append(f"matched {label.replace('_', ' ')} posture language")
            break

    urgency: list[str] = []
    if _immediate_safety_present(combined):
        urgency.append("immediate_safety")
    if _contains_any(combined, CHILD_SAFETY_TERMS, negation_aware=True):
        urgency.append("urgent_child_safety")
    if _contains_any(combined, ("served", "summons", "complaint", "received court papers", "got court papers"), negation_aware=True):
        urgency.append("served_papers")
    if _contains_any(combined, ("deadline", "due", "hearing", "tomorrow", "today", "this week", "next week"), negation_aware=True):
        urgency.append("possible_deadline")

    documents = [label for label, terms in DOCUMENT_PATTERNS.items() if _contains_any(combined, terms, negation_aware=True)]
    critical_dates = _extract_critical_dates(original, reference)
    dates = [str(item["raw"]) for item in critical_dates]
    docket_match = DOCKET_PATTERN.search(original)
    court_match = COURT_PATTERN.search(original)
    child_relevant = _contains_any(combined, ("child", "children", "parenting", "school", "therapy", "contact", "exchange", "custody"), negation_aware=True)
    target = _search_target(original, normalized, task)
    record_type_filter = "pdf" if task == "record_search" and re.search(r"\bpdfs?\b", normalized) else ""
    requested = _requested_actions(combined)
    selection = _source_selection(normalized)
    source_lane = _source_lane(normalized)
    attention = _attention_level(task, urgency, critical_dates, reference)
    continuation = _continuation_requested(normalized)

    if issues:
        reasons.append("identified topic signals: " + ", ".join(label.replace("_", " ") for label in issues[:3]))
    if critical_dates:
        reasons.append("extracted date or deadline language")
    if requested:
        reasons.append("identified requested action without deciding legal entitlement")
    if truncated:
        reasons.append(f"input was limited to {MAX_INTAKE_CHARS} characters for safe local processing")
        confidence = max(0.35, confidence - 0.08)
    confidence = min(0.99, confidence + min(0.04, 0.01 * len(issues)) + (0.02 if critical_dates else 0.0))

    goal_map = {
        "source_card_followup": "Reopen the prior answer's source cards without rerunning the search.",
        "record_search": f"Search the selected local records for {target or 'a specific term or phrase'}.",
        "corpus_inventory": "List the selected matter's indexed records and search-readiness status without running a Maine-law search.",
        "served_papers": "Understand the papers, preserve deadlines, and identify the first safe steps.",
        "immediate_safety": "Address immediate safety before routine case planning.",
        "child_safety": "Route an urgent child-safety concern without making unsupported conclusions.",
        "hearing_preparation": "Prepare for the listed court event and organize the relevant records.",
        "understand_order": "Explain the order in plain language while preserving the exact text for review.",
        "enforce_order": "Separate the order language, alleged events, proof, and possible procedural routes.",
        "modify_order": "Identify what change is requested and what current order and changed facts matter.",
        "child_support": "Clarify the support posture and identify the records and official materials needed.",
        "organize_records": "Turn the selected records into a searchable inventory, timeline, and evidence map.",
        "find_printable": "Find a relevant local family printable without treating it as legal authority.",
        "plain_language_explanation": "Provide a plain-language explanation grounded in the available source lane.",
        "general_question": "Answer the Maine family-law question with visible source limits.",
        "describe_situation": "Sort the situation into a useful question and next step.",
    }

    summary = IntakeSummary(
        normalized_text=normalized,
        task=task,
        issues=issues,
        procedural_posture=posture,
        urgency_flags=list(dict.fromkeys(urgency)),
        dates_mentioned=list(dict.fromkeys(dates)),
        critical_dates=critical_dates,
        documents_mentioned=documents,
        requested_actions=requested,
        search_target=target,
        record_type_filter=record_type_filter,
        source_card_selection=selection,
        source_card_lane=source_lane,
        docket_number=docket_match.group(1) if docket_match else "",
        court=court_match.group(1) if court_match else "",
        child_relevant=child_relevant,
        user_goal=goal_map.get(task, goal_map["general_question"]),
        routing_reasons=list(dict.fromkeys(reasons))[:6],
        attention_level=attention,
        confidence=round(confidence, 3),
        interpretation_note=(
            "This is a routing summary, not a legal or factual conclusion. Review the original papers, dates, and source cards."
        ),
        input_truncated=truncated,
        original_length=original_length,
        continuation_requested=continuation,
    )

    if prior_intake and continuation and task not in {
        "immediate_safety",
        "child_safety",
        "record_search",
        "source_card_followup",
    }:
        previous = (
            prior_intake
            if isinstance(prior_intake, IntakeSummary)
            else IntakeSummary.from_dict(prior_intake)
        )
        inheritable_tasks = {
            "served_papers",
            "hearing_preparation",
            "understand_order",
            "enforce_order",
            "modify_order",
            "child_support",
            "organize_records",
            "find_printable",
            "plain_language_explanation",
            "general_question",
            "describe_situation",
        }
        inherited: list[str] = []
        continuity_shell_tasks = {
            "general_question",
            "describe_situation",
            "plain_language_explanation",
            "organize_records",
        }
        if (
            summary.task in continuity_shell_tasks
            and not summary.issues
            and previous.task in inheritable_tasks
        ):
            summary.inherited_task = previous.task
            summary.task = previous.task
            inherited.append("task")
        if not summary.issues and previous.issues:
            summary.issues = list(previous.issues[:6])
            summary.inherited_issues = list(summary.issues)
            inherited.append("issue labels")
        if summary.procedural_posture == "unknown" and previous.procedural_posture != "unknown":
            summary.procedural_posture = previous.procedural_posture
            inherited.append("procedural posture")
        if not summary.requested_actions and previous.requested_actions:
            summary.requested_actions = list(previous.requested_actions[:4])
            inherited.append("requested action")
        if previous.child_relevant:
            summary.child_relevant = True
        if inherited:
            summary.context_inherited = True
            summary.continuity_reason = (
                "The short follow-up explicitly referred to the prior turn. Only structured routing labels were reused; "
                "no prior dates, docket numbers, court names, safety flags, or raw question text were inherited."
            )
            summary.routing_reasons = list(
                dict.fromkeys(
                    ["continued from the prior session routing anchor"] + summary.routing_reasons
                )
            )[:6]
            summary.user_goal = (
                f"Continue the prior {summary.task.replace('_', ' ')} discussion without treating prior facts as established."
            )
            summary.confidence = round(min(0.96, max(summary.confidence, 0.78)), 3)

    summary.essential_follow_up_questions = _follow_ups(summary)
    return summary


def concise_intake_label(summary: IntakeSummary) -> str:
    labels = {
        "source_card_followup": "prior source-card follow-up",
        "record_search": "local record search",
        "served_papers": "served papers / deadline triage",
        "immediate_safety": "immediate safety",
        "child_safety": "child-safety routing",
        "hearing_preparation": "hearing preparation",
        "understand_order": "order explanation",
        "enforce_order": "possible enforcement / existing-order issue",
        "modify_order": "possible change to an existing order",
        "child_support": "child-support question",
        "organize_records": "records and evidence organization",
        "find_printable": "family printable search",
        "plain_language_explanation": "plain-language explanation",
        "general_question": "Maine family-law information",
        "describe_situation": "situation sorting",
    }
    return labels.get(summary.task, summary.task.replace("_", " "))
