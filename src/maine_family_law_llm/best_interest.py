"""Deterministic Maine best-interest answer support.

The local workbench is intentionally source-backed and lightweight. This module
handles a high-value Maine family-law query that should not depend on generic
LLM memory: the 19-A M.R.S. § 1653(3) best-interest factors.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .retrieve import SearchResult


BEST_INTEREST_CITATION = "19-A M.R.S. § 1653(3)"

BEST_INTEREST_FACTORS: tuple[tuple[str, str], ...] = (
    ("A", "The age of the child."),
    ("B", "The relationship of the child with the child's parents and any other persons who may significantly affect the child's welfare."),
    ("C", "The preference of the child, if old enough to express a meaningful preference."),
    ("D", "The duration and adequacy of the child's current living arrangements and the desirability of maintaining continuity."),
    ("E", "The stability of any proposed living arrangements for the child."),
    ("F", "The motivation of the parties involved and their capacities to give the child love, affection and guidance."),
    ("G", "The child's adjustment to the child's present home, school and community."),
    ("H", "The capacity of each parent to allow and encourage frequent and continuing contact between the child and the other parent, including physical access."),
    ("I", "The capacity of each parent to cooperate or to learn to cooperate in child care."),
    ("J", "Methods for assisting parental cooperation and resolving disputes and each parent's willingness to use those methods."),
    ("K", "The effect on the child if one parent has sole authority over the child's upbringing."),
    ("L", "The existence of domestic abuse between the parents, past or current, and how that abuse affects the child emotionally, the child's safety, and the other factors."),
    ("M", "The existence of any history of child abuse by a parent."),
    ("N", "All other factors having a reasonable bearing on the physical and psychological well-being of the child."),
    ("O", "A parent's prior willful misuse of the protection from abuse process to gain tactical advantage, subject to clear-and-convincing-evidence and findings requirements."),
    ("P", "If the child is under one year of age, whether the child is being breast-fed."),
    ("Q", "The existence of a parent's conviction for a sex offense or sexually violent offense."),
    ("R", "If a person resides with a parent, whether that person has certain criminal, juvenile, or child-protection adjudication history involving sexual offenses."),
    ("S", "Whether allocation of some or all parental rights and responsibilities would best support the child's safety and well-being."),
)


@dataclass(frozen=True)
class SpecialAnswer:
    text: str
    citations: tuple[SearchResult, ...]


def is_best_interest_question(question: str) -> bool:
    text = question.lower()
    has_best_interest = bool(re.search(r"\bbest\s+interests?\b", text))
    has_factor_language = any(term in text for term in ("factor", "factors", "custody", "parental rights", "residence", "contact"))
    has_statute = "1653" in text or "19-a" in text or "19 a" in text
    return (has_best_interest and has_factor_language) or (has_statute and "factor" in text)


def source_supports_best_interest(result: SearchResult) -> bool:
    haystack = " ".join(
        [
            result.title,
            result.citation,
            result.snippet,
            str(result.metadata.get("citation_hint", "")),
            str(result.metadata.get("text", ""))[:2400],
        ]
    ).lower()
    return "1653" in haystack or ("best interest" in haystack and "parental rights" in haystack)


def compose_best_interest_answer(
    question: str,
    retrieval_results: tuple[SearchResult, ...],
    *,
    answer_style: str = "plain_language",
) -> SpecialAnswer | None:
    if not is_best_interest_question(question):
        return None
    supporting = tuple(result for result in retrieval_results if source_supports_best_interest(result))
    if not supporting:
        return None

    lines: list[str] = []
    if answer_style == "checklist":
        lines.append(f"Checklist: Maine best-interest factors under {BEST_INTEREST_CITATION}:")
    else:
        lines.append(
            f"Maine's best-interest factors for parental rights and responsibilities are in {BEST_INTEREST_CITATION}. "
            "For residence and parent-child contact decisions, the child's safety and well-being are primary."
        )
    lines.append("")
    for label, text in BEST_INTEREST_FACTORS:
        prefix = f"[ ] {label}." if answer_style == "checklist" else f"{label}."
        lines.append(f"{prefix} {text}")
    lines.extend(
        [
            "",
            "Review notes:",
            "- Do not treat this as filing-ready analysis; apply each factor to sourced facts and have a human reviewer check it.",
            "- Check the current official statute page before relying on the text.",
            "- If domestic abuse, protection-from-abuse history, child abuse, or sexual-offense facts are present, flag safety and contact conditions separately.",
        ]
    )
    return SpecialAnswer(text="\n".join(lines), citations=supporting[:3])
