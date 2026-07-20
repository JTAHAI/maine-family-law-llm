"""Deterministic local input hardening for chat and retrieval boundaries.

The workbench preserves ordinary legal text while neutralizing invisible Unicode
controls, null bytes, and oversized values that can spoof UI direction or create
ambiguous retrieval/session behavior. Reports contain counts and flags only;
they never copy the user's original text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

_BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d",
    "\u202e", "\u2066", "\u2067", "\u2068", "\u2069",
}
_ALLOWED_CONTROLS = {"\n", "\t"}
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SEARCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")


@dataclass(frozen=True)
class TextIntegrityResult:
    value: str
    original_length: int
    normalized_length: int
    max_length: int
    removed_control_count: int
    removed_bidi_count: int
    removed_null_count: int
    truncated: bool
    unicode_normalized: bool
    whitespace_normalized: bool

    @property
    def changed(self) -> bool:
        return any(
            (
                self.removed_control_count,
                self.removed_bidi_count,
                self.removed_null_count,
                self.truncated,
                self.unicode_normalized,
                self.whitespace_normalized,
            )
        )

    def report(self) -> dict[str, Any]:
        flags: list[str] = []
        if self.removed_bidi_count:
            flags.append("unicode_direction_controls_removed")
        if self.removed_control_count:
            flags.append("nonprinting_controls_removed")
        if self.removed_null_count:
            flags.append("null_bytes_removed")
        if self.truncated:
            flags.append("input_truncated_to_local_limit")
        if self.unicode_normalized:
            flags.append("unicode_nfkc_normalized")
        if self.whitespace_normalized:
            flags.append("whitespace_normalized")
        return {
            "original_length": self.original_length,
            "normalized_length": self.normalized_length,
            "max_length": self.max_length,
            "changed": self.changed,
            "truncated": self.truncated,
            "removed_control_count": self.removed_control_count,
            "removed_bidi_count": self.removed_bidi_count,
            "removed_null_count": self.removed_null_count,
            "flags": flags,
        }


def harden_text_input(
    value: object,
    *,
    max_length: int,
    preserve_newlines: bool = False,
) -> TextIntegrityResult:
    raw = str(value or "")
    original_length = len(raw)
    normalized = unicodedata.normalize("NFKC", raw.replace("\r\n", "\n").replace("\r", "\n"))
    unicode_normalized = normalized != raw

    kept: list[str] = []
    removed_control = 0
    removed_bidi = 0
    removed_null = 0
    for char in normalized:
        if char == "\x00":
            removed_null += 1
            continue
        if char in _BIDI_CONTROLS:
            removed_bidi += 1
            continue
        category = unicodedata.category(char)
        if category in {"Cc", "Cf"} and char not in _ALLOWED_CONTROLS:
            removed_control += 1
            continue
        kept.append(char)

    cleaned = "".join(kept)
    before_whitespace = cleaned
    if preserve_newlines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
        cleaned = "\n".join(line for line in lines if line).strip()
    else:
        cleaned = " ".join(cleaned.split())
    whitespace_normalized = cleaned != before_whitespace

    safe_limit = max(0, int(max_length))
    truncated = len(cleaned) > safe_limit
    if truncated:
        cleaned = cleaned[:safe_limit].rstrip()

    return TextIntegrityResult(
        value=cleaned,
        original_length=original_length,
        normalized_length=len(cleaned),
        max_length=safe_limit,
        removed_control_count=removed_control,
        removed_bidi_count=removed_bidi,
        removed_null_count=removed_null,
        truncated=truncated,
        unicode_normalized=unicode_normalized,
        whitespace_normalized=whitespace_normalized,
    )


def normalize_session_id(value: object) -> tuple[str, dict[str, Any]]:
    raw = str(value or "").strip()
    accepted = bool(_SESSION_RE.fullmatch(raw))
    return (
        raw if accepted else "",
        {
            "provided": bool(raw),
            "accepted": accepted,
            "reason": "accepted_opaque_local_identifier" if accepted else (
                "not_provided" if not raw else "invalid_session_identifier_format"
            ),
        },
    )


def normalize_search_id(value: object) -> tuple[str, dict[str, Any]]:
    raw = str(value or "").strip()
    accepted = bool(_SEARCH_ID_RE.fullmatch(raw))
    return (
        raw if accepted else "",
        {
            "provided": bool(raw),
            "accepted": accepted,
            "reason": "accepted_recent_search_identifier" if accepted else (
                "not_provided" if not raw else "invalid_search_identifier_format"
            ),
        },
    )
