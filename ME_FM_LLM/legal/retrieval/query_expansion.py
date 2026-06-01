from __future__ import annotations

import re

MAINE_FAMILY_LAW_SYNONYMS: dict[str, tuple[str, ...]] = {
    "custody": ("parental rights", "parental responsibilities", "primary residence", "contact"),
    "visitation": ("contact", "parenting time", "parent-child contact"),
    "parenting": ("parental rights", "parental responsibilities", "contact schedule"),
    "parental": ("custody", "parenting", "primary residence", "contact"),
    "responsibilities": ("custody", "parental rights", "best interest"),
    "support": ("child support", "spousal support", "support order"),
    "divorce": ("dissolution", "domestic relations", "family matter"),
    "pfa": ("protection from abuse", "abuse prevention", "protective order"),
    "protection": ("protection from abuse", "protection from harassment", "protective order"),
    "findings": ("Rule 52", "findings of fact", "best interest"),
    "appeal": ("Law Court", "standard of review", "preservation", "record"),
    "uccjea": ("jurisdiction", "home state", "child custody jurisdiction"),
    "form": ("FM", "court form", "judicial branch form"),
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "under",
    "what",
    "when",
    "with",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.I)


def tokenize(text: str, *, keep_stop_words: bool = False) -> tuple[str, ...]:
    tokens = tuple(token.lower() for token in TOKEN_PATTERN.findall(text))
    if keep_stop_words:
        return tokens
    return tuple(token for token in tokens if token not in STOP_WORDS and len(token) > 1)


def expand_query(query: str) -> tuple[str, ...]:
    """Return normalized query terms plus Maine-family-law synonyms.

    This is intentionally deterministic and local: it gives the retriever Maine practice
    vocabulary without relying on a generator or a network model.
    """

    terms = list(tokenize(query))
    lowered = query.lower()
    for trigger, expansions in MAINE_FAMILY_LAW_SYNONYMS.items():
        if trigger in lowered or trigger in terms:
            for phrase in expansions:
                terms.extend(tokenize(phrase))
    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        if term not in seen:
            ordered_terms.append(term)
            seen.add(term)
    return tuple(ordered_terms)
