"""Answer composition from retrieved sources only."""

from __future__ import annotations

from dataclasses import dataclass

from .best_interest import compose_best_interest_answer
from .chat_library import compose_library_answer
from .cite import render_citation_appendix
from .retrieve import SearchResult
from .safety import SafetyResult


DISCLAIMER = (
    "This is legal information, not legal advice. It does not create an "
    "attorney-client relationship."
)


@dataclass(frozen=True)
class ComposedAnswer:
    answer: str
    citations: tuple[SearchResult, ...]
    grounded: bool
    failure_class: str = "none"
    recovery_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "grounded": self.grounded,
            "failure_class": self.failure_class,
            "recovery_hint": self.recovery_hint,
            "citations": [item.to_dict() for item in self.citations],
        }


def compose_answer(
    question: str,
    retrieval_results: list[SearchResult] | tuple[SearchResult, ...],
    safety_result: SafetyResult,
    *,
    answer_style: str = "plain_language",
    matter_context: str = "",
) -> ComposedAnswer:
    results = tuple(retrieval_results)
    special = compose_best_interest_answer(question + " " + matter_context, results, answer_style=answer_style)
    if special is not None:
        body = special.text
        if DISCLAIMER.lower() not in body.lower():
            body += "\n\n" + DISCLAIMER
        body += "\n\n" + render_citation_appendix(special.citations)
        return ComposedAnswer(answer=body, citations=special.citations, grounded=True)

    library_answer = compose_library_answer(
        question,
        results,
        answer_style=answer_style,
        matter_context=matter_context,
    )
    if library_answer is not None:
        return ComposedAnswer(answer=library_answer.text, citations=library_answer.citations, grounded=True)

    if safety_result.category == "general" and not safety_result.requires_citations:
        return ComposedAnswer(
            answer="Hi. Ask a Maine family-law question and I will look for source-backed information.",
            citations=(),
            grounded=True,
        )
    if safety_result.requires_emergency_language:
        text = (
            "If anyone is in immediate danger, call 911. For protection-from-abuse or child-safety "
            "concerns, use official court or emergency resources rather than relying on an AI answer."
        )
        if results:
            text += "\n\n" + render_citation_appendix(results)
        return ComposedAnswer(answer=f"{text}\n\n{DISCLAIMER}", citations=results, grounded=bool(results))
    if safety_result.requires_citations and not results:
        return ComposedAnswer(
            answer=(
                "I cannot answer that legal/procedure/form question substantively because no "
                "supporting Maine source was retrieved. Add official sources and retry."
            ),
            citations=(),
            grounded=False,
            failure_class="sources_missing_for_legal_answer",
            recovery_hint="Run `mfl sources fetch --fixtures`, `mfl sources normalize --fixtures`, and `mfl index build --fixtures`.",
        )

    source_lines = []
    for result in results:
        kind = str(result.metadata.get("source_type", "source")).replace("_", " ")
        source_lines.append(f"- {kind}: {result.snippet}")
    body = "\n".join(
        [
            "Based on the retrieved source snippets:",
            *source_lines,
            "",
            "Practical next step: review the cited official source page or form instructions before acting.",
        ]
    )
    warnings = []
    if any(result.metadata.get("effective_date") or result.metadata.get("version_label") for result in results):
        warnings.append("Check the effective date and version label before relying on this information.")
    if safety_result.requires_disclaimer:
        warnings.append(DISCLAIMER)
    if warnings:
        body += "\n\n" + "\n".join(warnings)
    body += "\n\n" + render_citation_appendix(results)
    return ComposedAnswer(answer=body, citations=results, grounded=True)
