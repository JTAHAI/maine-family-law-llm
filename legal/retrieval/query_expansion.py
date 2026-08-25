from __future__ import annotations

import re
from dataclasses import dataclass

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
_NON_MAINE_JURISDICTION = re.compile(r"\b(new\s+hampshire|massachusetts|vermont|connecticut|rhode\s+island|new\s+york|federal|us\s+district|supreme\s+court)\b", re.I)
_MAINE_JURISDICTION = re.compile(r"\b(maine|me\.?\s+rev\.?\s+stat\.?|m\.r\.)\b", re.I)
_EXACT_REFERENCE = re.compile(r"\b(?:\d+\s+M\.R\.S\.\s*§?|M\.R\.\s+(?:Civ\.|Fam\.)?\s*P\.|FM-?\d+|ME\s+\d{4,})", re.I)


@dataclass(frozen=True)
class GuardedQueryExpansion:
    terms: tuple[str, ...]
    expansion_applied: bool
    jurisdiction_status: str
    exact_reference_preserved: bool
    guardrails: tuple[str, ...]

    def receipt(self) -> dict[str, object]:
        return {
            "expansion_applied": self.expansion_applied,
            "jurisdiction_status": self.jurisdiction_status,
            "exact_reference_preserved": self.exact_reference_preserved,
            "guardrails": list(self.guardrails),
            "expanded_term_count": len(self.terms),
            "review_required": True,
        }


def tokenize(text: str, *, keep_stop_words: bool = False) -> tuple[str, ...]:
    tokens = tuple(token.lower() for token in TOKEN_PATTERN.findall(text))
    if keep_stop_words:
        return tokens
    return tuple(token for token in tokens if token not in STOP_WORDS and len(token) > 1)


def expand_query_guarded(query: str) -> GuardedQueryExpansion:
    """Expand only Maine-family vocabulary without silently changing scope."""

    query = str(query or "")
    terms = list(tokenize(query))
    exact_reference = bool(_EXACT_REFERENCE.search(query))
    non_maine = bool(_NON_MAINE_JURISDICTION.search(query))
    maine = bool(_MAINE_JURISDICTION.search(query))
    guardrails: list[str] = []
    if non_maine:
        guardrails.append("non_maine_jurisdiction_detected_no_maine_synonyms_added")
    if exact_reference:
        guardrails.append("exact_reference_preserved")
    if not non_maine:
        lowered = query.lower()
        for trigger, expansions in MAINE_FAMILY_LAW_SYNONYMS.items():
            if trigger in lowered or trigger in terms:
                for phrase in expansions:
                    terms.extend(tokenize(phrase))
    else:
        guardrails.append("jurisdiction_review_required")
    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        if term not in seen:
            ordered_terms.append(term)
            seen.add(term)
    return GuardedQueryExpansion(
        terms=tuple(ordered_terms),
        expansion_applied=not non_maine and len(ordered_terms) > len(tokenize(query)),
        jurisdiction_status="maine_expansion_allowed" if maine or not non_maine else "non_maine_review_required",
        exact_reference_preserved=exact_reference,
        guardrails=tuple(guardrails),
    )


def expand_query(query: str) -> tuple[str, ...]:
    """Return normalized query terms plus Maine-family-law synonyms.

    This is intentionally deterministic and local: it gives the retriever Maine practice
    vocabulary without relying on a generator or a network model.
    """

    return expand_query_guarded(query).terms
