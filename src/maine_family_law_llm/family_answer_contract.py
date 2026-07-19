"""Structured, local-only family-justice answer contract.

The legacy ``answer`` string remains available for existing clients, but it is
rendered from this contract so the chat, export, and evidence surfaces cannot
quietly drift into competing answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


CHILD_TERMS = {
    "child", "children", "parenting", "school", "therapy", "exchange",
    "transportation", "sibling", "routine", "caregiver", "contact",
}
DEADLINE_TERMS = {"deadline", "served", "service", "hearing", "tomorrow", "today", "due"}


def _clean_lines(values: Iterable[object]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _source_summary(item: dict[str, Any], lane: str) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    metadata["source_lane"] = lane
    return {
        "source_id": str(item.get("source_id") or metadata.get("id") or "source"),
        "title": str(item.get("title") or metadata.get("title") or "Source"),
        "citation": str(item.get("citation") or metadata.get("citation_hint") or ""),
        "lane": lane,
        "authority_status": "private" if lane == "private_record" else ("official" if metadata.get("official", True) else "unofficial"),
        "jurisdiction": str(metadata.get("jurisdiction") or ("Maine" if lane == "legal_authority" else "")),
        "effective_or_retrieved": str(metadata.get("effective_date") or metadata.get("retrieved_at") or metadata.get("version_label") or "verify"),
        "freshness": str(metadata.get("freshness") or metadata.get("freshness_status") or "verify"),
        "matched_passage": str(item.get("snippet") or metadata.get("text_excerpt") or ""),
        "proposition": str(metadata.get("proposition") or ("Supports a statement of law." if lane == "legal_authority" else "Supports a factual matter record.")),
    }


def render_legacy_answer(contract: dict[str, Any]) -> str:
    """Render a readable compatible string from the structured answer only."""

    sections: list[tuple[str, list[str]]] = []
    meaning = str(contract.get("what_this_means") or "").strip()
    if meaning:
        sections.append(("What this means", [meaning]))
    for key, title in (
        ("what_to_do_right_now", "What to do right now"),
        ("next_three_steps", "Your next three steps"),
        ("what_to_gather", "What to gather"),
        ("what_may_be_missing", "What may be missing"),
        ("child_impact_lens", "What this may mean for your child"),
        ("when_to_get_human_help", "When to get human help"),
    ):
        values = _clean_lines(contract.get(key) or [])
        if values:
            sections.append((title, values))
    rendered: list[str] = []
    for title, values in sections:
        rendered.append(title + ":\n" + "\n".join(f"- {value}" for value in values))
    return "\n\n".join(rendered) or "No answer was returned."


def build_family_answer_contract(
    *,
    question: str,
    legacy_answer: str,
    citations: Iterable[dict[str, Any]],
    search_mode: str,
    safety: dict[str, Any] | None = None,
    missing_information: Iterable[object] = (),
    follow_up_questions: Iterable[object] = (),
    child_impact_enabled: bool = False,
    lane_grounding: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Create neutral, practical sections without turning records into law."""

    lowered = question.lower()
    safety = dict(safety or {})
    immediate_safety = bool(safety.get("requires_emergency_language"))
    possible_deadline = any(term in lowered for term in DEADLINE_TERMS)
    child_relevant = child_impact_enabled or any(term in lowered for term in CHILD_TERMS)
    law_sources: list[dict[str, Any]] = []
    record_sources: list[dict[str, Any]] = []
    for citation in citations:
        lane = str((citation.get("metadata") or {}).get("source_lane") or "legal_authority")
        summary = _source_summary(citation, lane)
        if lane == "private_record":
            record_sources.append(summary)
        else:
            law_sources.append(summary)

    now: list[str] = []
    if immediate_safety:
        now.append("If anyone is in immediate danger, call 911 or seek qualified local emergency help now.")
    if possible_deadline:
        now.append("Confirm the date, time, court, and service details from the original papers or official docket; do not rely on this chat alone for a deadline.")
    if not now:
        now.append("Slow down, keep the original documents together, and compare any important step with the cited source or qualified local help.")

    next_steps = [
        "Read the cited source or record passage before acting on it.",
        "Write down dates, names, and the exact question you still need answered.",
        "Use a clerk, lawyer, advocate, counselor, or navigator for the part that requires human judgment or official confirmation.",
    ]
    gather = ["The original order, notice, filing, or message that prompted the question.", "A short date-ordered timeline and copies of relevant communications."]
    missing = _clean_lines(missing_information) or _clean_lines(follow_up_questions)
    child_impact: list[str] = []
    if child_relevant:
        child_impact = [
            "Consider whether the next step protects routines, school, health or therapy logistics, exchanges, and important caregiver relationships.",
            "Keep adult conflict away from the child: do not ask a child to choose, carry messages, investigate, or take sides.",
            "A useful question is: what information would help the adults make the next step more predictable and less stressful for the child?",
        ]
    human_help = ["Get qualified local help promptly for safety concerns, a near deadline, served papers, or a court hearing."] if (immediate_safety or possible_deadline) else ["Get qualified local help when the source is unclear, facts are disputed, or a filing or safety decision is involved."]
    grounding = lane_grounding or {
        "legal_authority": bool(law_sources),
        "private_record": bool(record_sources),
    }
    return {
        "schema_version": "family_answer_v3",
        "what_this_means": legacy_answer.strip(),
        "what_to_do_right_now": now,
        "next_three_steps": next_steps,
        "what_to_gather": gather,
        "what_may_be_missing": missing,
        "child_impact_lens": child_impact,
        "maine_law_sources": law_sources,
        "private_record_sources": record_sources,
        "when_to_get_human_help": human_help,
        "safety_flags": {
            "immediate_safety_concern": immediate_safety,
            "possible_deadline": possible_deadline,
            "served_papers": "served" in lowered or "service" in lowered,
            "hearing_preparation": "hearing" in lowered,
            "protection_from_abuse_routing": "protection from abuse" in lowered or "pfa" in lowered,
            "urgent_child_safety_concern": "child safety" in lowered or "child is unsafe" in lowered,
        },
        "lane_grounding": grounding,
        "limits": [
            "Private records may support a factual statement about a matter; they are not legal authority.",
            "Legal authority may support a statement of law; it does not prove disputed family facts.",
        ],
    }
