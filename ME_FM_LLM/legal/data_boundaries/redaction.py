from __future__ import annotations

from dataclasses import dataclass

from legal.data_boundaries.private_data_scanner import DOB_RE, EMAIL_RE, PHONE_RE, SSN_RE


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redaction_count: int


def redact_private_identifiers(text: str) -> RedactionResult:
    redacted = text
    count = 0
    for pattern, replacement in [
        (SSN_RE, "[REDACTED_SSN]"),
        (DOB_RE, "[REDACTED_DOB]"),
        (EMAIL_RE, "[REDACTED_EMAIL]"),
        (PHONE_RE, "[REDACTED_PHONE]"),
    ]:
        redacted, replacements = pattern.subn(replacement, redacted)
        count += replacements
    return RedactionResult(text=redacted, redaction_count=count)
