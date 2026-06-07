from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


FACT_LABELS = {
    "user_stated",
    "source_supported",
    "evidence_supported",
    "unverified",
    "contradicted",
    "unknown",
}
SENSITIVE_FIELD_NAMES = {
    "address",
    "dob",
    "ssn",
    "minor_identifiers",
    "medical_details",
    "financial_account_numbers",
    "juvenile_details",
    "sealed_record_details",
}


def redact_sensitive_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[redacted-ssn]", text)
    text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "[redacted-date]", text)
    text = re.sub(r"\b\d{1,5}\s+[A-Za-z0-9 .'-]+\s+(Street|St|Road|Rd|Avenue|Ave|Lane|Ln)\b", "[redacted-address]", text)
    return text


@dataclass(frozen=True)
class SessionFact:
    label: str
    text: str
    source: str = "conversation"

    def __post_init__(self) -> None:
        if self.label not in FACT_LABELS:
            raise ValueError(f"invalid fact label: {self.label}")

    def as_dict(self) -> dict[str, str]:
        return {"label": self.label, "text": redact_sensitive_text(self.text), "source": self.source}


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": redact_sensitive_text(self.content),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class ConversationSessionState:
    session_id: str
    audience: str = "unknown"
    mode: str = "self_represented_plain_language"
    state: str = "new_session"
    unresolved_missing_information: list[dict[str, Any]] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    review_required: bool = True
    filing_ready_status: str = "blocked_from_filing_ready"
    facts: list[SessionFact] = field(default_factory=list)
    turns: list[ConversationTurn] = field(default_factory=list)
    max_turns: int = 12

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.turns.append(
            ConversationTurn(
                role=role,
                content=redact_sensitive_text(content),
                created_at=datetime.now(UTC).isoformat(),
                metadata=metadata or {},
            )
        )
        self.turns = self.turns[-self.max_turns :]

    def add_fact(self, text: str, *, label: str = "user_stated", source: str = "conversation") -> None:
        if text:
            self.facts.append(SessionFact(label=label, text=text, source=source))

    def merge_response(self, response: dict[str, Any]) -> None:
        self.audience = str(response.get("audience") or self.audience)
        self.mode = str(response.get("mode") or self.mode)
        self.unresolved_missing_information = list(response.get("missing_information") or self.unresolved_missing_information)
        self.red_flags = list(dict.fromkeys([*self.red_flags, *[str(item) for item in response.get("red_flags") or []]]))
        self.review_required = self.review_required or bool(response.get("review_required", True))
        next_filing_status = str(response.get("filing_ready_status") or self.filing_ready_status)
        if self.filing_ready_status != "filing_ready_passed":
            self.filing_ready_status = "blocked_from_filing_ready"
        elif next_filing_status != "filing_ready_passed":
            self.filing_ready_status = "blocked_from_filing_ready"

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "audience": self.audience,
            "mode": self.mode,
            "state": self.state,
            "unresolved_missing_information": self.unresolved_missing_information,
            "red_flags": self.red_flags,
            "review_required": self.review_required,
            "filing_ready_status": self.filing_ready_status,
            "facts": [fact.as_dict() for fact in self.facts],
            "turns": [turn.as_dict() for turn in self.turns],
        }


def safe_payload_facts(payload: dict[str, Any]) -> list[SessionFact]:
    facts: list[SessionFact] = []
    for key, value in sorted(payload.items()):
        if value in (None, "", [], {}, ()):
            continue
        if key in SENSITIVE_FIELD_NAMES:
            facts.append(SessionFact(label="user_stated", text=f"{key}: [sensitive detail omitted]", source="payload"))
            continue
        facts.append(SessionFact(label="user_stated", text=f"{key}: {redact_sensitive_text(str(value))}", source="payload"))
    return facts
