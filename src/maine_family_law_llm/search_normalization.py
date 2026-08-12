"""Safe, deterministic normalization for local record search.

The functions in this module only create search aliases. They never alter the
stored evidence text or the bytes presented in the record inspector.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Common Unicode dash/minus characters seen in Word exports, PDFs, email, and OCR.
_DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2015": "-",  # horizontal bar
        "\u2043": "-",  # hyphen bullet
        "\u2212": "-",  # minus sign
        "\ufe58": "-",  # small em dash
        "\ufe63": "-",  # small hyphen-minus
        "\uff0d": "-",  # full-width hyphen-minus
        "\u00ad": "",   # soft hyphen
    }
)

# A line-end hyphen may be either a word broken by OCR/layout (inter-\nference)
# or a real compound (well-\nbeing). Search aliases retain both readings.
_LINE_BREAK_HYPHEN = re.compile(r"(?<=[0-9A-Za-z])\s*-\s*(?:\r?\n|\u2028|\u2029)\s*(?=[0-9A-Za-z])")
_INLINE_DASH = re.compile(r"(?<=[0-9A-Za-z])\s*-\s*(?=[0-9A-Za-z])")
_NON_WORD = re.compile(r"[^0-9a-z_']+")
_WHITESPACE = re.compile(r"\s+")

SEARCH_STOPWORDS = frozenset(
    {
        "about",
        "all",
        "and",
        "contents",
        "could",
        "document",
        "documents",
        "does",
        "everything",
        "files",
        "find",
        "from",
        "have",
        "inside",
        "into",
        "list",
        "look",
        "matter",
        "mentions",
        "my",
        "pages",
        "pdf",
        "pdfs",
        "please",
        "records",
        "related",
        "search",
        "selected",
        "show",
        "should",
        "tell",
        "that",
        "the",
        "this",
        "what",
        "where",
        "with",
        "would",
    }
)


@dataclass(frozen=True, slots=True)
class SearchNormalization:
    original: str
    canonical: str
    compact: str
    terms: tuple[str, ...]
    hyphen_variant_used: bool


def _base(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).translate(_DASH_TRANSLATION)


def _word_space(value: str) -> str:
    lowered = value.casefold()
    lowered = _NON_WORD.sub(" ", lowered)
    return _WHITESPACE.sub(" ", lowered).strip()


def normalize_search_query(value: str) -> SearchNormalization:
    """Normalize a user search target while preserving a transparent audit trail."""

    original = str(value or "")
    base = _base(original)
    # A query hyphen is treated as a boundary so post-judgment, post judgment,
    # and postjudgment share the same terms.
    canonical = _word_space(_INLINE_DASH.sub(" ", base))
    compact = canonical.replace(" ", "")
    terms = tuple(
        dict.fromkeys(
            token
            for token in re.findall(r"[0-9a-z_']{2,}", canonical)
            if len(token) >= 3 and token not in SEARCH_STOPWORDS
        )
    )
    hyphen_variant_used = base != original or bool(_INLINE_DASH.search(base))
    return SearchNormalization(
        original=original,
        canonical=canonical,
        compact=compact,
        terms=terms,
        hyphen_variant_used=hyphen_variant_used,
    )


def build_search_alias_text(value: str) -> str:
    """Return bounded aliases used only for matching and FTS indexing.

    The first alias joins words broken across a line. The second preserves a
    word boundary. The third normalizes ordinary inline hyphens to spaces.
    This lets ``inter-\nference``, ``interference``, and ``parent-child`` be
    found without mutating the original record text.
    """

    base = _base(value)
    joined = _LINE_BREAK_HYPHEN.sub("", base)
    spaced = _LINE_BREAK_HYPHEN.sub(" ", base)
    inline_spaced = _INLINE_DASH.sub(" ", spaced)
    aliases = []
    for candidate in (joined, spaced, inline_spaced):
        normalized = _word_space(candidate)
        if normalized and normalized not in aliases:
            aliases.append(normalized)
    return "\n".join(aliases)


def normalized_match_text(value: str) -> str:
    """Return the combined alias text used for deterministic match checks."""

    return build_search_alias_text(value)


def normalized_snippet(value: str, needle: str, *, radius: int = 240) -> str:
    """Produce a readable snippet from original text around a normalized match."""

    # Repair layout/OCR line-break hyphenation for display snippets only. The
    # source inspector continues to show the original verified text.
    original = _WHITESPACE.sub(" ", _LINE_BREAK_HYPHEN.sub("", _base(value))).strip()
    if not original:
        return ""
    normalized_original = normalize_search_query(original).canonical
    normalized_needle = normalize_search_query(needle).canonical
    if not normalized_needle:
        return original[: radius * 2]
    position = normalized_original.find(normalized_needle)
    if position < 0:
        first_term = next(iter(normalize_search_query(needle).terms), "")
        position = normalized_original.find(first_term) if first_term else -1
    if position < 0:
        return original[: radius * 2]
    # Normalization changes offsets, so use the relative position as a safe
    # approximation rather than claiming exact quote offsets.
    ratio = position / max(len(normalized_original), 1)
    center = min(len(original), max(0, int(round(ratio * len(original)))))
    start = max(0, center - radius)
    end = min(len(original), center + radius)
    prefix = "… " if start else ""
    suffix = " …" if end < len(original) else ""
    return f"{prefix}{original[start:end].strip()}{suffix}"
