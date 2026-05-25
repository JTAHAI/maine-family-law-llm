"""Safe draft helpers that produce outlines, not filing-ready documents."""

from __future__ import annotations

from dataclasses import dataclass

from .answer import DISCLAIMER
from .cite import render_citation_appendix
from .retrieve import SearchResult


ALLOWED_DRAFT_MODES = {
    "checklist",
    "question_list",
    "court_form_prep_notes",
    "attorney_review_packet",
    "clerk_question_packet",
}


@dataclass(frozen=True)
class DraftResult:
    text: str
    citations: tuple[SearchResult, ...]
    failure_class: str = "none"
    recovery_hint: str = ""


def draft_from_sources(
    request: str,
    retrieval_results: list[SearchResult] | tuple[SearchResult, ...],
    *,
    mode: str = "checklist",
) -> DraftResult:
    if mode not in ALLOWED_DRAFT_MODES:
        raise ValueError(f"bad draft mode: {mode}")
    results = tuple(retrieval_results)
    if not results:
        return DraftResult(
            text="I cannot draft even an informational outline without retrieved Maine sources.",
            citations=(),
            failure_class="sources_missing_for_draft",
            recovery_hint="Build the fixture index or add official sources before drafting.",
        )
    lines = [
        f"Draft mode: {mode}",
        "Status: informational outline only; review required; not filing-ready.",
        DISCLAIMER,
        "",
        "Source-backed notes:",
    ]
    for result in results:
        lines.append(f"- Review {result.title}: {result.snippet}")
    lines.extend(
        [
            "",
            "Questions to verify before any filing:",
            "- Which official form or process page applies?",
            "- Has the court page or statute changed since the listed version/effective date?",
            "- Should a Maine attorney review the facts and next steps?",
            "",
            render_citation_appendix(results),
        ]
    )
    return DraftResult(text="\n".join(lines), citations=results)
